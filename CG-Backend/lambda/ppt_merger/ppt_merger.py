"""
PPT Merger Lambda Function

NEW ARCHITECTURE:
Loads batch structure files, generates final HTML, and creates ONE PPT from complete HTML.
This ensures all images load correctly and callout positioning matches HTML layout.
"""

import json
import boto3
import logging
import os
import re
from datetime import datetime
from typing import Dict, List

# Import local HTML and PPT conversion functions
from html_generator import generate_html_from_structure
from html_to_ppt_converter import convert_html_to_pptx_new
from mark_overflow_slides import mark_overflow_slides

s3_client = boto3.client('s3', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def fix_image_only_slides(slides: List[Dict], is_spanish: bool) -> List[Dict]:
    """
    Fix slides that only have an image block with no accompanying text.
    AI sometimes creates image-only slides despite instructions.
    Adds generic descriptive bullets beside the image.
    
    This function is applied in the MERGER (not InfographicGenerator) because:
    - Batches generate slides independently
    - Fix must run on complete merged set to catch all image-only slides
    """
    fixed_slides = []
    fixed_count = 0
    
    for slide in slides:
        content_blocks = slide.get('content_blocks', [])
        
        # Check if this is an image-only slide
        if len(content_blocks) == 1 and content_blocks[0].get('type') == 'image':
            image_block = content_blocks[0]
            slide_title = slide.get('title', '')
            
            # Create descriptive bullets - extract key terms from title
            # Remove continuation markers like "(cont. 2)"
            clean_title = re.sub(r'\s*\(cont\.?\s*\d*\)', '', slide_title, flags=re.IGNORECASE)
            clean_title = re.sub(r'\s*\(Part\s*\d+\)', '', clean_title, flags=re.IGNORECASE)
            
            bullets = {
                'type': 'bullets',
                'heading': '',  # No heading - bullets are self-explanatory
                'items': [
                    f"Componente esencial del ecosistema" if is_spanish else "Essential ecosystem component",
                    f"Integración con otros servicios" if is_spanish else "Integration with other services",
                    f"Características principales" if is_spanish else "Main features",
                    f"Casos de uso comunes" if is_spanish else "Common use cases"
                ]
            }
            
            # Reorder: bullets first, then image (for image-right layout)
            # Or keep image first for image-left layout
            layout = slide.get('layout_hint', 'image-right')
            if 'image-right' in layout:
                slide['content_blocks'] = [bullets, image_block]
            else:  # image-left
                slide['content_blocks'] = [image_block, bullets]
            
            fixed_count += 1
            logger.warning(f"🔧 Fixed image-only slide: '{slide_title}' - added {len(bullets['items'])} bullets")
        
        fixed_slides.append(slide)
    
    if fixed_count > 0:
        logger.info(f"✅ Fixed {fixed_count} image-only slides by adding descriptive bullets")
    
    return fixed_slides


def lambda_handler(event, context):
    """
    Merge PPT batch results into final presentation.
    
    NEW ARCHITECTURE:
    1. Load all batch structure files
    2. Merge into complete structure
    3. Generate final HTML from complete structure
    4. Create ONE PPT from final HTML
    5. Clean up intermediate batch files
    """
    try:
        logger.info(f"🚀 Starting PPT merger")
        
        # Extract parameters
        course_bucket = event.get('course_bucket')
        project_folder = event.get('project_folder')
        ppt_batch_results = event.get('ppt_batch_results', [])
        action = event.get('action', 'merge_and_convert')  # Options: 'merge_and_convert', 'merge_to_html', 'convert_to_ppt'
        input_html_key = event.get('html_s3_key')  # For convert_to_ppt action
        
        logger.info(f"🚀 Starting PPT merger (Action: {action})")
        logger.info(f"📚 Course: {project_folder}")
        
        # SHARED: Load final structure (needed for all actions)
        final_structure_key = f"{project_folder}/infographics/infographic_structure.json"
        merged_structure = None
        
        # ---------------------------------------------------------
        # PHASE 1: MERGE & GENERATE HTML
        # ---------------------------------------------------------
        if action in ['merge_and_convert', 'merge_to_html']:
            logger.info(f"📦 Batches completed: {len(ppt_batch_results)}")
            
            # With incremental approach, all batches append to the SAME shared structure file
            # We only need to load the FINAL structure once, not from each batch result
            logger.info(f"📄 Loading final shared structure...")
            
            # Get the structure key from the LAST batch result (all batches use the same file)
            if ppt_batch_results:
                last_batch_result = ppt_batch_results[-1]
                
                if isinstance(last_batch_result, str):
                    logger.error("❌ Old format detected - batches must return structure keys")
                    # Try to use default key
                    temp_key = final_structure_key
                elif 'statusCode' in last_batch_result and 'body' in last_batch_result:
                    # Lambda response format
                    body_str = last_batch_result.get('body', '{}')
                    body_data = json.loads(body_str) if isinstance(body_str, str) else body_str
                    temp_key = body_data.get('structure_s3_key')
                else:
                    # Direct dict format
                    temp_key = last_batch_result.get('structure_s3_key')
                
                if temp_key:
                    final_structure_key = temp_key
            
            # Load the FINAL complete structure (incremental file from all batches)
            try:
                structure_response = s3_client.get_object(Bucket=course_bucket, Key=final_structure_key)
                merged_structure = json.loads(structure_response['Body'].read().decode('utf-8'))
                
                all_slides = merged_structure.get('slides', [])
                total_lessons = len(set(s.get('lesson_number') for s in all_slides if s.get('lesson_number') is not None))
                
                logger.info(f"✅ Loaded final structure: {final_structure_key}")
                logger.info(f"   Total slides: {len(all_slides)}")
                logger.info(f"   Total lessons: {total_lessons}")
                
                # FIX: Apply image-only slide fix to MERGED structure
                # (batches generate slides independently, fix must run on complete merged set)
                logger.info(f"🔧 Checking for image-only slides in merged structure...")
                image_only_count = sum(
                    1 for slide in all_slides
                    if len(slide.get('content_blocks', [])) == 1 
                    and slide['content_blocks'][0].get('type') == 'image'
                )
                
                if image_only_count > 0:
                    logger.warning(f"⚠️ Found {image_only_count} image-only slides - applying fix")
                    fixed_slides = fix_image_only_slides(all_slides, is_spanish=True)
                    merged_structure['slides'] = fixed_slides
                    all_slides = fixed_slides  # Update reference
                    logger.info(f"✅ Fixed all image-only slides")
                else:
                    logger.info(f"✅ No image-only slides found - structure is clean")
                
            except Exception as e:
                logger.error(f"❌ Error loading final structure: {str(e)}")
                raise
            
            # Update merged structure metadata
            merged_structure['completion_status'] = 'complete'
            merged_structure['merge_timestamp'] = datetime.utcnow().isoformat()
            
            # Save final merged structure with updated metadata
            s3_client.put_object(
                Bucket=course_bucket,
                Key=final_structure_key,
                Body=json.dumps(merged_structure, indent=2, ensure_ascii=False),
                ContentType='application/json'
            )
            logger.info(f"   ✓ Saved merged structure: {final_structure_key}")
            
            # Generate final HTML from complete structure
            logger.info(f"🌐 Generating final HTML from merged structure...")
            final_html = generate_html_from_structure(merged_structure)
            
            # OVERFLOW DETECTION: JavaScript in HTML will mark overflow slides client-side
            # (Server-side Python estimation was too conservative with false positives)
            # JavaScript uses actual scrollHeight measurement - 100% accurate
            logger.info(f"✅ HTML generated with JavaScript overflow detection (client-side)")
            
            # Save final HTML
            final_html_key = f"{project_folder}/infographics/infographic_final.html"
            s3_client.put_object(
                Bucket=course_bucket,
                Key=final_html_key,
                Body=final_html.encode('utf-8'),
                ContentType='text/html; charset=utf-8'
            )
            logger.info(f"   ✓ Saved final HTML: {final_html_key}")
            
            # Clean up intermediate batch files
            logger.info(f"🧹 Cleaning up intermediate batch files...")
            deleted_count = 0
            try:
                response = s3_client.list_objects_v2(
                    Bucket=course_bucket,
                    Prefix=f"{project_folder}/infographics/"
                )
                for obj in response.get('Contents', []):
                    key = obj['Key']
                    if 'batch_' in key and (key.endswith('.html') or key.endswith('.json') or key.endswith('.pptx')):
                        s3_client.delete_object(Bucket=course_bucket, Key=key)
                        deleted_count += 1
                logger.info(f"✅ Deleted {deleted_count} intermediate batch files")
            except Exception as e:
                logger.warning(f"   ⚠️ Could not clean up batch files: {e}")

            # If action is just merge_to_html, return here
            if action == 'merge_to_html':
                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'message': 'HTML generation completed successfully',
                        'html_s3_key': final_html_key,
                        'structure_s3_key': final_structure_key,
                        'total_slides': merged_structure['total_slides'],
                        'course_bucket': course_bucket,
                        'project_folder': project_folder
                    })
                }
                
        # ---------------------------------------------------------
        # PHASE 2: CONVERT TO PPT
        # ---------------------------------------------------------
        if action in ['merge_and_convert', 'convert_to_ppt']:
            # Determine which HTML to use
            if action == 'convert_to_ppt':
                if not input_html_key:
                    raise ValueError("html_s3_key is required for convert_to_ppt action")
                final_html_key = input_html_key
                logger.info(f"🔄 Converting provided HTML: {final_html_key}")
                
                # Load structure if not already loaded
                if not merged_structure:
                    try:
                        logger.info(f"📄 Loading structure for PPT conversion: {final_structure_key}")
                        structure_response = s3_client.get_object(Bucket=course_bucket, Key=final_structure_key)
                        merged_structure = json.loads(structure_response['Body'].read().decode('utf-8'))
                    except Exception as e:
                        logger.error(f"❌ Error loading structure: {str(e)}")
                        raise
            
            # Load HTML content
            logger.info(f"📥 Loading HTML content from: {final_html_key}")
            html_response = s3_client.get_object(Bucket=course_bucket, Key=final_html_key)
            final_html = html_response['Body'].read().decode('utf-8')
            
            # Generate ONE PPT from final HTML
            logger.info(f"📊 Converting final HTML to PPT...")
            pptx_bytes = convert_html_to_pptx_new(
                html_content=final_html,
                structure=merged_structure,
                course_bucket=course_bucket,
                project_folder=project_folder,
                s3_client=s3_client  # CRITICAL: Pass S3 client for image downloads
            )
            
            # Save final PPT
            output_s3_key = f"{project_folder}/infographics/{project_folder}.pptx"
            s3_client.put_object(
                Bucket=course_bucket,
                Key=output_s3_key,
                Body=pptx_bytes,
                ContentType='application/vnd.openxmlformats-officedocument.presentationml.presentation'
            )
            logger.info(f"✅ Saved final PPT: {output_s3_key}")
            logger.info(f"   Total slides in PPT: {merged_structure.get('total_slides', 0)}")
            logger.info(f"   Output: s3://{course_bucket}/{output_s3_key}")
            
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'PPT generation completed successfully',
                    'ppt_s3_key': output_s3_key,
                    'html_s3_key': final_html_key,
                    'structure_s3_key': final_structure_key,
                    'total_slides': merged_structure.get('total_slides', 0),
                    's3_url': f"s3://{course_bucket}/{output_s3_key}"
                })
            }
    
    except Exception as e:
        logger.error(f"❌ Error in PPT merger: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }
