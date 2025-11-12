#!/bin/bash
# Increase deployment capacity to allow more requests
# Each capacity unit = 10 req/min + 1K tokens/min
# Capacity 10 = 100 req/min + 10K tokens/min

DEPLOYMENT_NAME="gpt-4o-mini"
RESOURCE_NAME="WPSGAPINSTANCE"
RESOURCE_GROUP="ollamama-mcp-rg"
NEW_CAPACITY=10  # Adjust this number as needed

echo "Current capacity: 1"
echo "Increasing to capacity: $NEW_CAPACITY"
echo "This will give you: $((NEW_CAPACITY * 10)) requests/min and $((NEW_CAPACITY * 1000)) tokens/min"
echo ""
echo "Run this command:"
echo "az cognitiveservices account deployment update \\"
echo "  --name $RESOURCE_NAME \\"
echo "  --resource-group $RESOURCE_GROUP \\"
echo "  --deployment-name $DEPLOYMENT_NAME \\"
echo "  --sku Standard \\"
echo "  --capacity $NEW_CAPACITY"
