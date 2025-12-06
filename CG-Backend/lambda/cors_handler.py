#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CORS handler for API Gateway OPTIONS requests.
Returns appropriate CORS headers for preflight requests.
"""

import json

def lambda_handler(event, context):
    """
    Handle CORS preflight OPTIONS requests.
    """
    return {
        "statusCode": 200,
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,x-amz-content-sha256",
            "Access-Control-Allow-Methods": "OPTIONS,GET,POST,PUT,DELETE",
            "Access-Control-Max-Age": "86400"
        },
        "body": ""
    }