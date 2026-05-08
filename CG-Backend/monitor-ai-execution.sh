#!/bin/bash
EXECUTION_ARN="arn:aws:states:us-east-1:471112982547:execution:PptBatchOrchestrationStateMachine:ppt-orchestration-251031-databricks-ciencia-datos-20251121-162931"

echo "🔍 Monitoring execution..."
while true; do
    STATUS=$(aws stepfunctions describe-execution --execution-arn "$EXECUTION_ARN" --query 'status' --output text 2>/dev/null || echo "PENDING")
    
    echo "$(date '+%H:%M:%S') - Status: $STATUS"
    
    if [ "$STATUS" = "SUCCEEDED" ] || [ "$STATUS" = "FAILED" ] || [ "$STATUS" = "TIMED_OUT" ] || [ "$STATUS" = "ABORTED" ]; then
        echo ""
        echo "✅ Execution finished: $STATUS"
        
        if [ "$STATUS" = "SUCCEEDED" ]; then
            echo ""
            echo "📊 Checking final HTML..."
            aws s3 ls s3://crewai-course-artifacts/251031-databricks-ciencia-datos/infographics/infographic_final.html --human-readable
            
            echo ""
            echo "📥 Downloading and analyzing HTML..."
            aws s3 cp s3://crewai-course-artifacts/251031-databricks-ciencia-datos/infographics/infographic_final.html /tmp/final_ai.html 2>&1 | grep -v "Completed"
            
            if [ -f /tmp/final_ai.html ]; then
                echo ""
                echo "📈 HTML Stats:"
                echo "  File size: $(wc -c < /tmp/final_ai.html) bytes"
                echo "  Total slides: $(grep -c 'class="slide"' /tmp/final_ai.html)"
                echo ""
                echo "🔍 Checking for AI Web Designer evidence:"
                grep -o "Web Designer" /tmp/final_ai.html | wc -l | xargs echo "  'Web Designer' mentions:"
                echo ""
                echo "⚠️  Checking for overflow warnings:"
                if grep -q "overflow" /tmp/final_ai.html; then
                    echo "  Found overflow mentions - checking if they're warnings or CSS classes..."
                    grep "overflow" /tmp/final_ai.html | head -n 3
                else
                    echo "  ✅ No overflow detected!"
                fi
            fi
        fi
        
        break
    fi
    
    sleep 10
done
