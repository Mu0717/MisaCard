"""
txt 文件解析器
支持解析格式：
1. 卡密:01013bd7-f16b-44ad-a806-c4d61ea6a9fc 额度:0 有效期:1小时 卡头:5236xx
2. 卡密: mio-f3dc27e4-e853-429a-9e4b-3294af7c25ca 额度: 1 有效期: 1小时
3. 纯卡密格式: mio-xxx 或 uuid
4. LR格式: 卡密:LR-890DA88EC1F3 额度:0 有效期:1小时 卡头:4462
5. 新LR格式: 卡密:LR-F8E6FF0D7146-USA 额度:0 有效期:1小时 卡头:4866
"""
import re
from typing import List, Dict, Optional


def parse_card_line(line: str) -> Optional[Dict]:
    """
    解析单行卡片数据

    支持多种格式：
    1. 带卡头格式：卡密:xxx 额度:x 有效期:x小时 卡头:xxx
    2. 完整格式：卡密: mio-xxx 额度: 1 有效期: 1小时
    2. 完整格式：卡密: mio-xxx 额度: 1 有效期: 1小时
    3. LR格式：卡密:LR-xxx 额度:0 有效期:1小时 卡头:xxx
    4. 仅卡密：mio-xxx (使用默认额度0和有效期1小时)

    Args:
        line: 包含卡片信息的文本行

    Returns:
        解析后的字典，包含 card_id, card_limit, validity_hours, card_header(可选)
        如果解析失败返回 None
    """
    line = line.strip()
    if not line:
        return None

    # 方式1: 尝试匹配带卡头的格式：卡密:xxx 额度:xxx 有效期:xxx小时 卡头:xxx
    # 注意：冒号后可能没有空格
    full_with_header_pattern = r'卡密:\s*([^\s]+)\s+额度:\s*(\d+(?:\.\d+)?)\s+有效期:\s*(\d+)\s*小时\s+卡头:\s*([^\s]+)'
    match = re.search(full_with_header_pattern, line)

    if match:
        card_id = match.group(1).strip()
        card_limit = float(match.group(2))
        validity_hours = int(match.group(3))
        card_header = match.group(4).strip()

        # 验证卡密格式
        if validate_card_id(card_id):
            return {
                "card_id": card_id,
                "card_limit": card_limit,
                "validity_hours": validity_hours,
                "card_header": card_header
            }

    # 方式2: 尝试匹配不带卡头的完整格式：卡密: xxx 额度: xxx 有效期: xxx小时
    full_pattern = r'卡密:\s*([^\s]+)\s+额度:\s*(\d+(?:\.\d+)?)\s+有效期:\s*(\d+)\s*小时'
    match = re.search(full_pattern, line)

    if match:
        card_id = match.group(1).strip()
        card_limit = float(match.group(2))
        validity_hours = int(match.group(3))

        # 验证卡密格式
        if validate_card_id(card_id):
            return {
                "card_id": card_id,
                "card_limit": card_limit,
                "validity_hours": validity_hours,
                "card_header": None
            }

    # 3. 尝试搜索特定后缀格式 (Mio, Cursor等)
    # 支持 mio-UUID, 纯 UUID, 以及 Cursor 格式 (XXXX-...-Cursor)
    # 优先匹配 Cursor 格式，防贪婪
    cursor_pattern = r'(?:卡密:\s*)?([A-Za-z0-9-]+\-Cursor)\b'
    match = re.search(cursor_pattern, line)
    if match:
        card_id = match.group(1).strip()
        if validate_card_id(card_id):
             return {
                "card_id": card_id,
                "card_limit": 0.0,
                "validity_hours": 1,
                "card_header": None
            }
            
    # 原有的 UUID 匹配
    card_id_pattern = r'(?:卡密:\s*)?((?:mio-)?[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})'
    match = re.search(card_id_pattern, line, re.IGNORECASE)

    if match:
        card_id = match.group(1).strip()

        # 验证卡密格式
        if validate_card_id(card_id):
            # 只有卡密时，使用默认值
            return {
                "card_id": card_id,
                "card_limit": 0.0,  # 默认额度0（激活后从API获取实际额度）
                "validity_hours": 1,  # 默认有效期1小时
                "card_header": None
            }

    return None


def parse_txt_file(content: str) -> tuple[List[Dict], List[str]]:
    """
    解析整个 txt 文件内容

    Args:
        content: txt 文件的完整内容

    Returns:
        (成功解析的卡片列表, 失败的行列表)
    """
    lines = content.split('\n')
    parsed_cards = []
    failed_lines = []

    for line_num, line in enumerate(lines, 1):
        if not line.strip():
            continue

        parsed = parse_card_line(line)
        if parsed:
            parsed_cards.append(parsed)
        else:
            failed_lines.append(f"第{line_num}行: {line.strip()}")

    return parsed_cards, failed_lines


def validate_card_id(card_id: str) -> bool:
    """
    验证卡密格式是否正确

    Args:
        card_id: 卡密字符串

    Returns:
        True 如果格式正确，否则 False
    """
    # 移除可能的 mio- 前缀进行检查
    clean_id = card_id.lower()
    if clean_id.startswith('mio-'):
        clean_id = clean_id[4:]

    # 1. 检查是否是 UUID 格式（带连字符）
    uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    if re.match(uuid_pattern, clean_id):
        return True
        
    # 3. 检查由 HolyMasterCard 提供的格式，现在改为 -Cursor 后缀
    # 示例: AWCC-9SW5-ZYVV-7XUY-AS5C-Cursor
    if card_id.endswith('-Cursor'):
        # 简单验证：只要由字母、数字、连字符组成，且长度合理
        # 去掉 -Cursor 后应该有内容
        prefix = card_id[:-7]
        if not prefix:
            return False
            
        # 检查是否只包含允许的字符 (A-Z, 0-9, -)
        if re.match(r'^[A-Za-z0-9-]+$', prefix):
            return True

    # 4. 检查 LR- 开头的格式
    # 示例: LR-890DA88EC1F3 或 LR-F8E6FF0D7146-USA
    if card_id.startswith('LR-'):
        # 简单验证：LR- 后跟字母、数字和连字符
        if re.match(r'^LR-[A-Z0-9-]+$', card_id):
            return True

    return False


def format_card_info(card_data: Dict) -> str:
    """
    格式化卡片信息为可读文本

    Args:
        card_data: 卡片数据字典

    Returns:
        格式化后的文本
    """
    return f"卡密: {card_data['card_id']} 额度: {card_data['card_limit']} 有效期: {card_data['validity_hours']}小时"
