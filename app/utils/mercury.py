import httpx
from typing import Dict, Any, Optional

MERCURY_REDEEM_URL = "https://actcard.xyz/api/keys/redeem"
MERCURY_QUERY_URL = "https://actcard.xyz/api/keys/query"

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
        "origin": "https://actcard.xyz",
        "pragma": "no-cache",
        "priority": "u=1, i",
        "referer": "https://actcard.xyz/redeem",
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
        # Step 1: Query the key status first
        try:
            query_response = await client.post(MERCURY_QUERY_URL, json=payload, headers=headers)
            query_data = query_response.json()
            
            # If success is True, it means the card is already active
            if query_data.get("success") is True:
                return query_data
                
            # If success is False and error is "卡密未使用" (Card unused), proceed to redeem
            if query_data.get("success") is False and query_data.get("error") == "卡密未使用":
                pass # Continue to redeem
            else:
                # If it's another error (e.g. invalid key), return the query result
                return query_data
                
        except Exception as e:
            # If query fails network-wise, maybe we should try redeem or just raise?
            # For now, let's log/print and try redeem or just re-raise. 
            # Given the script nature, if query fails, redeem likely fails too or we shouldn't proceed.
            # But to be safe and robust, let's assume if query crashes, we abort.
            # However, to match previous behavior, if something goes wrong with query that isn't the specific "unused" case, 
            # we might return the error.
            print(f"Error checking key status: {e}")
            return {"success": False, "error": f"Network/Query Error: {str(e)}"}

        # Step 2: Redeem if unused
        response = await client.post(MERCURY_REDEEM_URL, json=payload, headers=headers)
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
