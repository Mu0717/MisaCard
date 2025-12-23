import httpx
from typing import Dict, Any, Optional

MERCURY_API_URL = "https://mercury.wxie.de/api/keys/redeem"

async def redeem_key(key_id: str) -> Dict[str, Any]:
    """
    激活卡密 (Redeem Key) via Mercury API
    
    Args:
        key_id: The key ID to redeem.
        
    Returns:
        JSON response from the API.
    """
    headers = {
        "accept": "*/*",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
        "cache-control": "no-cache",
        "content-type": "application/json",
        "origin": "https://mercury.wxie.de",
        "pragma": "no-cache",
        "priority": "u=1, i",
        "referer": "https://mercury.wxie.de/redeem",
        "sec-ch-ua": '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
    }

    payload = {"key_id": key_id}

    async with httpx.AsyncClient() as client:
        # Note: http2=True helps in mimicking the browser's HTTP/2 behavior if the server supports it,
        # otherwise it falls back to HTTP/1.1.
        response = await client.post(MERCURY_API_URL, json=payload, headers=headers)
        
        # Raise for status to ensure we catch HTTP errors
        # response.raise_for_status() 
        # We might want to return the JSON even if it's an error status, depending on API behavior.
        # But generally, let's just return the json.
        
        return response.json()

if __name__ == "__main__":
    import asyncio
    
    async def main():
        # Example usage
        try:
            # Replace with a real key for testing if known, or use a dummy one
            res = await redeem_key("your_test_key_id")
            print(res)
        except Exception as e:
            print(f"Error: {e}")

    asyncio.run(main())
