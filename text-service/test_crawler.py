#!/usr/bin/env python
import os
import sys
import json
import requests
import time
import asyncio
import httpx
from src.core.service.image_to_ai_service import ImageToAIService

def test_crawler():
    # Step 1: Call crawler API
    print("Step 1: Calling crawler API...")
    crawler_url = "http://9.134.132.205:3002/v1/crawl"
    payload = {
        "url": "https://www.qq.com",
        "limit": 2000,
        "scrapeOptions": {
            "formats": ["markdown"]
        }
    }
    
    print(f"Making POST request to: {crawler_url}")
    print(f"With payload: {json.dumps(payload, indent=2)}")
    
    response = requests.post(
        crawler_url,
        headers={"Content-Type": "application/json"},
        json=payload
    )
    
    if not response.ok:
        print(f"Crawler API request failed: {response.status_code}, {response.text}")
        return
        
    crawler_data = response.json()
    print(f"Crawler API response: {json.dumps(crawler_data, indent=2)}")
    
    # Step 2: Get the result using the URL from crawler response
    print("\nStep 2: Getting crawler result...")
    result_url = crawler_data.get('url', '')
    if not result_url:
        print("No URL found in crawler response")
        return
        
    # Convert https to http as specified in the requirements
    http_url = result_url.replace("https://", "http://")
    print(f"Making request to: {http_url}")
    
    # Try to get with retries for scraping status
    max_retries = 10  # Increased from 5 to 10
    retry_count = 0
    
    while retry_count < max_retries:
        result_response = requests.get(http_url)
        
        if not result_response.ok:
            print(f"Failed to get crawler result: {result_response.status_code}, {result_response.text}")
            return
            
        result_data = result_response.json()
        print(f"Current status: {result_data.get('status')}")
        
        # Log data size even during scraping
        data_list = result_data.get('data', [])
        print(f"Data length: {len(data_list)}")
        if data_list:
            print(f"First data element keys: {list(data_list[0].keys())}")
        
        # Check if scraping is complete
        if result_data.get('status') == 'completed':
            print("Status is 'completed', breaking loop")
            break
        
        # If still scraping, wait and retry
        if result_data.get('status') == 'scraping':
            print(f"Scraping in progress, waiting before retry... (Attempt {retry_count+1}/{max_retries})")
            retry_count += 1
            time.sleep(5)  # Increased from 3 to 5 seconds
            continue
            
        # If we have data, break the loop
        if data_list and len(data_list) > 0 and any(d.get('markdown') for d in data_list):
            print("Found markdown data, breaking loop")
            break
            
        # Otherwise increment retry counter
        retry_count += 1
        time.sleep(3)  # Increased from 2 to 3 seconds
    
    # Print result data structure overview
    print("\nStep 3: Result data overview:")
    print(f"success: {result_data.get('success')}")
    print(f"status: {result_data.get('status')}")
    print(f"data length: {len(result_data.get('data', []))}")
    
    # Step 4: Extract markdown content
    print("\nStep 4: Extracting markdown content...")
    data_list = result_data.get('data', [])
    if not data_list:
        print("No data found in crawler result")
        return
    
    # Check if markdown exists in any data element
    markdown_found = False
    for i, item in enumerate(data_list):
        if 'markdown' in item:
            markdown_found = True
            markdown_content = item.get('markdown', '')
            print(f"Markdown found in item {i}")
            print(f"Markdown content (first 200 chars): {markdown_content[:200]}...")
            break
    
    if not markdown_found:
        print("No markdown found in any data items")
        print("Available keys in first data item:", list(data_list[0].keys()) if data_list else "No data items")
        return
    
    # Step 5: Print full data for diagnosis
    print("\nStep 5: Complete response data:")
    print(json.dumps(result_data, indent=2))

async def test_process_url():
    """Test the process_url method of ImageToAIService"""
    print("=== Testing ImageToAIService.process_url ===")
    
    # Create an instance of the service
    service = ImageToAIService()
    
    # Test URL (from the example in api.md)
    test_url = "https://cfm.qq.com/web201801/detail.shtml?docid=7924797936662049421"
    
    try:
        # Call the process_url method
        result = await service.process_url(test_url)
        
        # Validate the response structure
        if not isinstance(result, dict):
            print("❌ Error: Result is not a dictionary")
            return False
        
        if "code" not in result or result["code"] != 200:
            print(f"❌ Error: Missing or invalid 'code' field: {result.get('code')}")
            return False
        
        if "data" not in result or not isinstance(result["data"], list):
            print("❌ Error: Missing or invalid 'data' field")
            return False
        
        if "msg" not in result:
            print("❌ Error: Missing 'msg' field")
            return False
        
        # Check if data contains at least one item
        if len(result["data"]) == 0:
            print("❌ Error: 'data' list is empty")
            return False
        
        # Check the structure of the first data item
        first_item = result["data"][0]
        if "text" not in first_item or "img" not in first_item:
            print("❌ Error: Data item missing 'text' or 'img' fields")
            return False
        
        # Print a sample of the first few data items (up to 3)
        print("\nSample of processed data:")
        for i, item in enumerate(result["data"][:3]):
            print(f"Item {i+1}:")
            print(f"  Text: {item['text'][:100]}..." if len(item['text']) > 100 else f"  Text: {item['text']}")
            print(f"  Image: {item['img']}")
        
        print(f"\nTotal items: {len(result['data'])}")
        print("✅ Test passed: Response structure is valid")
        return True
        
    except Exception as e:
        print(f"❌ Error during test: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def test_api_endpoint():
    """Test the API endpoint using httpx directly"""
    print("\n=== Testing API Endpoint (/image-to-ai/crawler) ===")
    
    # Create an HTTP client
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        # Test URL (from the example in api.md)
        payload = {
            "url": "https://cfm.qq.com/web201801/detail.shtml?docid=7924797936662049421"
        }
        
        try:
            # Send a POST request to the endpoint
            response = await client.post("/image-to-ai/crawler", json=payload)
            
            # Check response status code
            if response.status_code != 200:
                print(f"❌ Error: Unexpected status code: {response.status_code}")
                print(f"Response: {response.text}")
                return False
            
            # Parse the response JSON
            result = response.json()
            
            # Validate the response structure
            if "code" not in result or result["code"] != 200:
                print(f"❌ Error: Missing or invalid 'code' field: {result.get('code')}")
                return False
            
            if "data" not in result or not isinstance(result["data"], list):
                print("❌ Error: Missing or invalid 'data' field")
                return False
            
            if "msg" not in result:
                print("❌ Error: Missing 'msg' field")
                return False
            
            # Print a sample of the first few data items (up to 3)
            print("\nSample of API response data:")
            for i, item in enumerate(result["data"][:3]):
                print(f"Item {i+1}:")
                print(f"  Text: {item['text'][:100]}..." if len(item['text']) > 100 else f"  Text: {item['text']}")
                print(f"  Image: {item['img']}")
            
            print(f"\nTotal items: {len(result['data'])}")
            print("✅ Test passed: API endpoint response is valid")
            return True
            
        except Exception as e:
            print(f"❌ Error during API test: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

async def main():
    # Test the service directly
    service_test_result = await test_process_url()
    
    # Only test the API endpoint if the service test passed
    # Note: The API server must be running for this test to work
    if service_test_result:
        print("\nService test passed. Would you like to test the API endpoint?")
        print("Note: The API server must be running on http://localhost:8000")
        response = input("Test API endpoint? (y/n): ")
        
        if response.lower() == 'y':
            await test_api_endpoint()
        else:
            print("Skipping API endpoint test.")
    
    print("\nAll tests completed.")

if __name__ == "__main__":
    asyncio.run(main()) 