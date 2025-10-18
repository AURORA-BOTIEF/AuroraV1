"""
Phase Coordinator Lambda Function
==================================
Implements CSMA-like protocol for coordinating API calls across concurrent modules.

This ensures minimum 60-second spacing between expensive operations to prevent
throttling while allowing efficient parallel processing.

Protocol:
1. Before expensive API call: Acquire lock
2. Check if another module is in same phase
3. If yes and < 60s elapsed: Wait
4. If yes and >= 60s elapsed: Proceed
5. If no: Proceed immediately
6. After API call: Release lock

Phases coordinated:
- ContentGen (Bedrock API)
- ImagesGen (Gemini API)
- LabPlanner (Bedrock API)
- LabWriter (Bedrock API)
"""

import boto3
import time
import random
import os
from datetime import datetime
from typing import Dict, Any

dynamodb = boto3.resource('dynamodb')
TABLE_NAME = 'course-generation-phase-locks'

# Dynamic delay configuration based on module count
# For 1-4 modules: 120 seconds (proven reliable for small courses)
# For 5-8 modules: 240 seconds (prevents batch overlaps with lesson batching)
MIN_DELAY_SMALL_COURSE = 120  # 1-4 modules
MIN_DELAY_LARGE_COURSE = 240  # 5-8 modules
MODULE_COUNT_THRESHOLD = 4

# Jitter to prevent thundering herd (seconds)
MAX_JITTER_SECONDS = 5


def get_min_delay(total_modules: int) -> int:
    """
    Calculate minimum delay based on total module count.
    
    Rationale:
    - Small courses (1-4 modules): 120s spacing is sufficient
    - Large courses (5-8 modules): 180s spacing prevents cumulative TPM quota exhaustion
    
    Args:
        total_modules: Total number of modules in the course
        
    Returns:
        Minimum delay in seconds
    """
    if total_modules <= MODULE_COUNT_THRESHOLD:
        return MIN_DELAY_SMALL_COURSE
    else:
        return MIN_DELAY_LARGE_COURSE


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Coordinates access to expensive API phases.
    
    Args:
        event: {
            "action": "acquire" | "release",
            "phase_name": "ContentGen" | "ImagesGen" | "LabPlanner" | "LabWriter",
            "module_number": 1,
            "execution_id": "course-gen-xxx",
            "total_modules": 8  # Optional: Total modules in course for dynamic delay
        }
    
    Returns:
        For acquire: {
            "statusCode": 200,
            "can_proceed": true/false,
            "wait_seconds": 0-180,
            "reason": "..."
        }
        For release: {
            "statusCode": 200,
            "message": "Lock released"
        }
    """
    action = event.get('action')
    phase_name = event.get('phase_name')
    module_number = event.get('module_number')
    execution_id = event.get('execution_id', 'unknown')
    total_modules = event.get('total_modules', 4)  # Default to small course if not specified
    
    print(f"PhaseCoordinator: action={action}, phase={phase_name}, module={module_number}, execution={execution_id}, total_modules={total_modules}")
    
    table = dynamodb.Table(TABLE_NAME)
    
    if action == "acquire":
        return acquire_lock(table, phase_name, module_number, execution_id, total_modules)
    elif action == "release":
        return release_lock(table, phase_name, module_number)
    else:
        return {
            'statusCode': 400,
            'error': f'Invalid action: {action}'
        }


def acquire_lock(table, phase_name: str, module_number: int, execution_id: str, total_modules: int) -> Dict[str, Any]:
    """
    Attempt to acquire lock for a phase.
    Implements CSMA-like "listen before talk" protocol with dynamic delay.
    
    Args:
        table: DynamoDB table resource
        phase_name: Name of the phase (ContentGen, ImagesGen, LabWriter, LabPlanner)
        module_number: Current module number
        execution_id: Execution identifier
        total_modules: Total number of modules in the course
    
    Returns:
        Dict with can_proceed, wait_seconds, and reason
    """
    try:
        # Get dynamic minimum delay based on course size
        min_delay_seconds = get_min_delay(total_modules)
        
        print(f"  Using MIN_DELAY={min_delay_seconds}s for {total_modules} modules")
        
        # Check if another module is currently in this phase
        response = table.get_item(Key={'phase_name': phase_name})
        
        if 'Item' in response:
            # Another module is using this phase
            existing_module = response['Item']['module_number']
            existing_start = int(response['Item']['start_timestamp'])  # Convert Decimal to int
            current_time = int(time.time() * 1000)  # milliseconds
            elapsed_ms = current_time - existing_start
            elapsed_seconds = elapsed_ms / 1000.0
            
            print(f"  Found existing lock: module={existing_module}, elapsed={elapsed_seconds:.1f}s")
            
            if elapsed_seconds < min_delay_seconds:
                # Need to wait
                wait_seconds = min_delay_seconds - elapsed_seconds
                # Add jitter to prevent thundering herd
                jitter = random.uniform(0, MAX_JITTER_SECONDS)
                total_wait = int(wait_seconds) + 1 + int(jitter)  # +1 for safety margin
                
                print(f"  Module {module_number} must wait {total_wait}s (base={wait_seconds:.1f}s, jitter={jitter:.1f}s)")
                
                return {
                    'statusCode': 200,
                    'can_proceed': False,
                    'wait_seconds': total_wait,
                    'reason': f'Module {existing_module} is in {phase_name} (elapsed: {elapsed_seconds:.1f}s)'
                }
            else:
                # Enough time has passed, can proceed
                print(f"  Sufficient time elapsed ({elapsed_seconds:.1f}s >= {min_delay_seconds}s)")
        
        # Can proceed - try to acquire lock atomically
        # CRITICAL: Must use atomic write that prevents race conditions
        # Even if multiple modules check simultaneously and see "no lock",
        # only ONE can successfully write due to ConditionExpression
        current_timestamp = int(time.time() * 1000)
        
        try:
            # First, try to acquire the lock if it doesn't exist
            table.put_item(
                Item={
                    'phase_name': phase_name,
                    'module_number': module_number,
                    'execution_id': execution_id,
                    'start_timestamp': current_timestamp,
                    'ttl': int(time.time()) + 3600,  # Auto-expire after 1 hour
                    'acquired_at': datetime.utcnow().isoformat()
                },
                ConditionExpression='attribute_not_exists(phase_name) OR #ts < :min_ts',
                ExpressionAttributeNames={
                    '#ts': 'start_timestamp'
                },
                ExpressionAttributeValues={
                    # Only overwrite if existing lock is older than MIN_DELAY
                    ':min_ts': current_timestamp - (min_delay_seconds * 1000)
                }
            )
        except table.meta.client.exceptions.ConditionalCheckFailedException:
            # Another module acquired the lock between our check and this put
            # This is a race condition - need to check again and wait
            print(f"  ⚠️  Module {module_number} lost race for {phase_name} lock, need to retry")
            
            # Re-check the lock to get accurate wait time
            response = table.get_item(Key={'phase_name': phase_name})
            if 'Item' in response:
                existing_module = response['Item']['module_number']
                existing_start = int(response['Item']['start_timestamp'])
                current_time = int(time.time() * 1000)
                elapsed_ms = current_time - existing_start
                elapsed_seconds = elapsed_ms / 1000.0
                
                # Calculate how much longer to wait
                # If lock holder hasn't finished their delay period, wait for remaining time
                # Otherwise, they should release soon, wait a full delay cycle
                remaining_delay = min_delay_seconds - elapsed_seconds
                
                if remaining_delay > 0:
                    # Lock holder still has time, wait for them to finish + small buffer
                    wait_seconds = remaining_delay + 10  # Extra buffer for lock release
                else:
                    # Lock holder should have released by now
                    # Either they're still running or about to release
                    # Wait a full delay cycle to be safe
                    wait_seconds = min_delay_seconds
                
                jitter = random.uniform(0, MAX_JITTER_SECONDS)
                total_wait = int(wait_seconds) + int(jitter)
                
                print(f"  Module {module_number} waiting {total_wait}s (elapsed={elapsed_seconds:.1f}s, remaining={remaining_delay:.1f}s)")
                
                return {
                    'statusCode': 200,
                    'can_proceed': False,
                    'wait_seconds': total_wait,
                    'reason': f'Lost race to module {existing_module}, must wait'
                }
            else:
                # Lock disappeared (released), retry immediately
                return {
                    'statusCode': 200,
                    'can_proceed': False,
                    'wait_seconds': 3,  # Short retry
                    'reason': 'Lock state changed, retry soon'
                }
        
        
        print(f"  ✅ Module {module_number} acquired lock for {phase_name}")
        
        return {
            'statusCode': 200,
            'can_proceed': True,
            'wait_seconds': 0,
            'reason': 'Lock acquired successfully'
        }
        
    except Exception as e:
        print(f"  ❌ Error acquiring lock: {e}")
        # Fail-open: Allow to proceed if coordination fails
        # Better to risk minor throttling than block execution
        return {
            'statusCode': 200,
            'can_proceed': True,
            'wait_seconds': 0,
            'reason': f'Lock acquisition failed (fail-open): {str(e)}'
        }


def release_lock(table, phase_name: str, module_number: int) -> Dict[str, Any]:
    """
    Release lock after completing a phase.
    """
    try:
        # Only delete if this module owns the lock
        table.delete_item(
            Key={'phase_name': phase_name},
            ConditionExpression='module_number = :mn',
            ExpressionAttributeValues={':mn': module_number}
        )
        
        print(f"  ✅ Module {module_number} released lock for {phase_name}")
        
        return {
            'statusCode': 200,
            'message': 'Lock released successfully'
        }
        
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        # Lock doesn't belong to this module (probably already expired or taken by another)
        print(f"  ⚠️  Module {module_number} doesn't own lock for {phase_name} (already released or expired)")
        return {
            'statusCode': 200,
            'message': 'Lock already released or expired'
        }
        
    except Exception as e:
        print(f"  ❌ Error releasing lock: {e}")
        # Not critical if release fails (TTL will clean up)
        return {
            'statusCode': 200,
            'message': f'Lock release failed (will auto-expire): {str(e)}'
        }
