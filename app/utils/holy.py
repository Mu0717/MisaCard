import httpx
from typing import Dict, Any

HOLY_ACTIVATE_URL = "http://holymastercard.com/api/license/activate"

async def redeem_holy_key(license_key: str) -> Dict[str, Any]:
    """
    激活卡密 (HolyMasterCard)
    
    Args:
        license_key: The license key to redeem (without -Holy suffix).
        
    Returns:
        JSON response from the API.
    """
    # 确保去除可能残留的后缀
    # 旧规则兼容 -Holy，新规则 -Cursor
    # 兼容包含额外信息的格式 (例如: "KEY 额度:0 ...")
    if " " in license_key:
        license_key = license_key.split()[0]

    # 确保去除可能残留的后缀
    # 旧规则兼容 -Holy，新规则 -Cursor，以及特殊后缀 -44622, -4866
    real_key = license_key.replace("-Cursor", "").replace("-Holy", "").replace("-44622", "").replace("-4866", "")
    
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "MisaCard/1.0"
    }

    payload = {"licenseKey": real_key}

    async with httpx.AsyncClient() as client:
        try:
            print(f"[Holy] Activating key: {real_key}")
            response = await client.post(HOLY_ACTIVATE_URL, json=payload, headers=headers, timeout=30.0)
            return response.json()
        except Exception as e:
            print(f"[Holy] Error activating key: {e}")
            return {"success": False, "error": f"Network Error: {str(e)}"}
