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

# Minimum delay between API calls (seconds)
MIN_DELAY_SECONDS = 60

# Jitter to prevent thundering herd (seconds)
MAX_JITTER_SECONDS = 5


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Coordinates access to expensive API phases.
    
    Args:
        event: {
            "action": "acquire" | "release",
            "phase_name": "ContentGen" | "ImagesGen" | "LabPlanner" | "LabWriter",
            "module_number": 1,
            "execution_id": "course-gen-xxx"
        }
    
    Returns:
        For acquire: {
            "statusCode": 200,
            "can_proceed": true/false,
            "wait_seconds": 0-60,
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
    
    print(f"PhaseCoordinator: action={action}, phase={phase_name}, module={module_number}, execution={execution_id}")
    
    table = dynamodb.Table(TABLE_NAME)
    
    if action == "acquire":
        return acquire_lock(table, phase_name, module_number, execution_id)
    elif action == "release":
        return release_lock(table, phase_name, module_number)
    else:
        return {
            'statusCode': 400,
            'error': f'Invalid action: {action}'
        }


def acquire_lock(table, phase_name: str, module_number: int, execution_id: str) -> Dict[str, Any]:
    """
    Attempt to acquire lock for a phase.
    Implements CSMA-like "listen before talk" protocol.
    """
    try:
        # Check if another module is currently in this phase
        response = table.get_item(Key={'phase_name': phase_name})
        
        if 'Item' in response:
            # Another module is using this phase
            existing_module = response['Item']['module_number']
            existing_start = response['Item']['start_timestamp']
            current_time = int(time.time() * 1000)  # milliseconds
            elapsed_ms = current_time - existing_start
            elapsed_seconds = elapsed_ms / 1000.0
            
            print(f"  Found existing lock: module={existing_module}, elapsed={elapsed_seconds:.1f}s")
            
            if elapsed_seconds < MIN_DELAY_SECONDS:
                # Need to wait
                wait_seconds = MIN_DELAY_SECONDS - elapsed_seconds
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
                print(f"  Sufficient time elapsed ({elapsed_seconds:.1f}s >= {MIN_DELAY_SECONDS}s)")
        
        # Can proceed - acquire lock
        table.put_item(
            Item={
                'phase_name': phase_name,
                'module_number': module_number,
                'execution_id': execution_id,
                'start_timestamp': int(time.time() * 1000),
                'ttl': int(time.time()) + 3600,  # Auto-expire after 1 hour
                'acquired_at': datetime.utcnow().isoformat()
            }
        )
        
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
