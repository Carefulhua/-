"""发票 PDF 文本解析（invoice-renamer.py 与 invoice-to-excel.py 共用）。

价税合计优先按"价税合计（大写）"的中文大写金额解析：PDF 文字流顺序不稳定，
"（小写）"标签后面紧跟的往往是"合计金额"而不是"价税合计"，直接取小写数字会取错。
"""
import re
import sys

# 中文大写数字
_CN_DIGITS = {
    '零': 0, '壹': 1, '贰': 2, '叁': 3, '肆': 4,
    '伍': 5, '陆': 6, '柒': 7, '捌': 8, '玖': 9,
}
_CN_UNITS = {'拾': 10, '佰': 100, '仟': 1000}
_CN_DIGIT_CHARS = '零壹贰叁肆伍陆柒捌玖'

# 大写金额，允许字符间被插入空白（pypdf 常见）
_CN_AMOUNT_RE = re.compile(
    r'[' + _CN_DIGIT_CHARS + r'拾佰仟万亿]\s*'
    r'[' + _CN_DIGIT_CHARS + r'拾佰仟万亿]{0,20}\s*[圆元]'
    r'(?:\s*[' + _CN_DIGIT_CHARS + r'角分整正]){0,6}'
)

MAX_ITEM_NAME_LEN = 30


def setup_console():
    """统一控制台输出为 UTF-8，避免 Windows 控制台编码不支持 emoji 时崩溃。"""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            try:
                stream.reconfigure(encoding='utf-8', errors='replace')
            except (ValueError, OSError):
                pass

# 品名行里出现这些词说明已经到了表头/合计区域
_STOP_WORDS = {
    '规格型号', '单位', '数量', '单价', '金额', '税率', '征收率', '税额',
    '合计', '价税合计', '备注', '开票人', '名称', '购买方', '销售方',
}
_UNIT_WORDS = {
    '台', '个', '次', '张', '件', '套', '只', '箱', '瓶', '份', '辆', '条',
    '本', '枚', '把', '支', '块', '盒', '包', '米', '吨', '千克', '克',
}


def parse_cn_amount(text):
    """把中文大写金额转成金额字符串，如 '贰佰肆拾叁圆壹角整' -> '243.10'。

    无法解析时返回 None。
    """
    text = text.replace('元', '圆').replace('整', '').replace('正', '')
    integer_part, _, fraction_part = text.partition('圆')

    total = 0       # 已结算的"亿/万"部分
    section = 0     # 当前万级以内的部分
    number = 0
    for ch in integer_part:
        if ch in _CN_DIGITS:
            number = _CN_DIGITS[ch]
        elif ch in _CN_UNITS:
            section += (number or 1) * _CN_UNITS[ch]
            number = 0
        elif ch == '万':
            total += (section + number) * 10000
            section = 0
            number = 0
        elif ch == '亿':
            total = (total + section + number) * 100000000
            section = 0
            number = 0
        else:
            return None
    integer_value = total + section + number

    jiao = re.search(r'([' + _CN_DIGIT_CHARS + r'])角', fraction_part)
    fen = re.search(r'([' + _CN_DIGIT_CHARS + r'])分', fraction_part)
    fraction = 0.0
    if jiao:
        fraction += _CN_DIGITS[jiao.group(1)] * 0.1
    if fen:
        fraction += _CN_DIGITS[fen.group(1)] * 0.01

    return f'{integer_value + fraction:.2f}'


def _find_cn_total_amount(text):
    """从"价税合计（大写）"附近的中文大写金额取价税合计。"""
    matches = list(_CN_AMOUNT_RE.finditer(text))
    if not matches:
        return None

    # 优先取"价税合计"标签之后出现的大写金额
    label = re.search(r'价\s*税\s*合\s*计', text)
    if label:
        for m in matches:
            if m.start() > label.start():
                amount = parse_cn_amount(re.sub(r'\s+', '', m.group(0)))
                if amount:
                    return amount

    for m in matches:
        amount = parse_cn_amount(re.sub(r'\s+', '', m.group(0)))
        if amount:
            return amount
    return None


def _find_total_amount(text):
    """价税合计提取核心逻辑。"""
    # --- 策略1: 中文大写金额（最可靠，不受 PDF 文字流顺序影响）---
    amount = _find_cn_total_amount(text)
    if amount:
        return amount

    # --- 策略2: 在"小写"附近找金额 ---
    # 格式B先试: "小写）¥339.00"（¥前数字后，经纪代理发票）
    # 优先于格式A，因为格式B匹配的"¥X"在"小写"上下文中无歧义
    # 而格式A的"X¥"可能匹配到错误的小计金额
    m = re.search(r'小\s*写.{0,80}?¥\s*(\d+\.\d{1,2})', text, re.DOTALL)
    if m:
        return m.group(1)
    # 格式A: "小写）16.43¥"（数字前¥后，滴滴出行发票）
    m = re.search(r'小\s*写.{0,80}?(\d+\.\d{1,2})\s*¥', text, re.DOTALL)
    if m:
        return m.group(1)

    # --- 策略3: 在"价税合计"附近找金额 ---
    m = re.search(r'价\s*税\s*合\s*计.{0,80}?(\d+\.\d{1,2})\s*¥', text, re.DOTALL)
    if m:
        return m.group(1)
    m = re.search(r'价\s*税\s*合\s*计.{0,80}?¥\s*(\d+\.\d{1,2})', text, re.DOTALL)
    if m:
        return m.group(1)

    # --- 策略4: 启发式兜底 ---
    # 收集所有 X.XX¥ 格式金额（数字在¥前）
    x_yen = re.findall(r'(\d+\.\d{1,2})\s*¥', text)
    # 收集所有 ¥X.XX 格式金额（¥在数字前）
    yen_x = re.findall(r'¥\s*(\d+\.\d{1,2})', text)

    # 情况A: 连续三个 X¥ 金额（餐饮发票: 金额小计/价税合计/税额）
    if len(x_yen) >= 3:
        amounts = [float(a.replace(',', '')) for a in x_yen[-3:]]
        # 三个金额中，中间那个最大 → 中间是价税合计
        if amounts[1] > amounts[0] and amounts[1] > amounts[2]:
            return str(amounts[1])

    # 情况B: ¥X 格式，取最大合理值（通常是价税合计）
    if yen_x:
        nums = [float(a.replace(',', '')) for a in yen_x]
        nums = [n for n in nums if n < 10000]
        if nums:
            return str(max(nums))

    # 情况C: X¥ 格式，取最大合理值
    if x_yen:
        nums = [float(a.replace(',', '')) for a in x_yen]
        nums = [n for n in nums if n < 10000]
        if nums:
            return str(max(nums))

    return ''


def _is_ascii_alnum(ch):
    return ('0' <= ch <= '9') or ('a' <= ch <= 'z') or ('A' <= ch <= 'Z')


def _truncate_name(name, limit):
    """按词边界截断，避免把 "Wi-Fi"、"XDR1500" 这类词截成半个。"""
    if len(name) <= limit:
        return name
    cut = name[:limit]
    if _is_ascii_alnum(cut[-1]) and _is_ascii_alnum(name[limit]):
        idx = limit
        while idx > 0 and _is_ascii_alnum(name[idx - 1]):
            idx -= 1
        if idx > 0:
            cut = name[:idx].rstrip('-_/')
    return cut.rstrip('-_/ ')


def _is_stop_token(token, has_name):
    if not token:
        return True
    if re.match(r'^[\d¥￥%\-+.,]', token):
        return True
    if token in _STOP_WORDS or token in _UNIT_WORDS:
        return True
    # 已经取到品名后又出现纯英文/型号串，说明进入了规格型号列
    if has_name and re.fullmatch(r'[A-Za-z0-9\-_]{6,}', token):
        return True
    return False


def _extract_item_name(text):
    """提取 "*类别*品名" 形式的项目名称。"""
    m = re.search(r'\*([^*\n]{1,20})\*([^\n]*)', text)
    if not m:
        return ''

    category = m.group(1).strip()
    tail = text[m.start(2):m.start(2) + 160]
    tokens = [t for t in re.split(r'\s+', tail) if t]

    name = ''
    for token in tokens:
        if _is_stop_token(token, bool(name)):
            break
        # 英文/型号后面紧跟中文时保留一个空格，其余直接拼接（PDF 换行会切断中文词）
        candidate = token if not name else name + token
        if len(candidate) > MAX_ITEM_NAME_LEN:
            if not name:
                name = _truncate_name(token, MAX_ITEM_NAME_LEN)
            break
        name = candidate

    if not name:
        return category
    return f'{category}*{name}'


def extract_invoice_info(text):
    """从 PDF 文本中提取发票信息。"""
    # 统一空白字符，处理 \xa0、\u3000 等特殊空格
    text = re.sub(r'[\xa0\u3000]', ' ', text)
    # 全角￥→半角¥统一（pypdf 输出全角，但正则用半角）
    text = text.replace('￥', '¥')

    # 发票号码
    invoice_number = ''
    match = re.search(r'发票号码[：:\s]*([A-Z0-9]{8,20})', text, re.IGNORECASE)
    if match:
        invoice_number = match.group(1).strip()

    # 火车票号码 (20位数字)
    if not invoice_number:
        match = re.search(r'\b(\d{20})\b', text)
        if match:
            invoice_number = match.group(1).strip()

    total_amount = _find_total_amount(text)

    # 火车票/打的 - 尝试匹配 "XX元" 格式（兜底）
    if not total_amount:
        match = re.search(r'(\d+\.?\d*)\s*元', text)
        if match:
            total_amount = match.group(1)

    # 火车票金额（在_find_total_amount之后补充尝试）
    # pypdf 常在中日文间插入空格，所以用 \s* 处理可能的空格
    if not total_amount or total_amount == '0':
        match = re.search(r'票\s*价\s*[：:]\s*[¥￥]?\s*([\d,]+\.?\d*)', text)
        if match:
            total_amount = match.group(1)

    # 退票费（铁路电子客票退票，格式: "退票费: ... ￥ 2.00"）
    if not total_amount or total_amount == '0':
        match = re.search(r'退\s*票\s*费\s*[：:].*?¥\s*(\d+\.\d{1,2})', text, re.DOTALL)
        if match:
            total_amount = match.group(1)

    # 统一金额格式为2位小数
    if total_amount and total_amount != '0':
        try:
            total_amount = f'{float(total_amount.replace(",", "")):.2f}'
        except ValueError:
            pass

    item_name = _extract_item_name(text)

    # 标准格式
    if not item_name:
        match = re.search(
            r'(?:项目名称|货物或应税劳务名称|服务名称)[：:\s]*([\u4e00-\u9fa5*][^\n\r]{2,30})',
            text,
        )
        if match:
            matched = match.group(1).strip()
            if not any(x in matched for x in ['规格型号', '单位', '数量', '单价']):
                item_name = matched

    # 火车票: 提取车次和区间
    if not item_name:
        # 车次
        train_num = re.search(r'\b([GDCKTZ]\d{1,4})\b', text)

        # 火车站名
        station_match = re.search(r'([\u4e00-\u9fa5]{2,6})(?:站|至|→)([\u4e00-\u9fa5]{2,6})', text)

        if station_match:
            item_name = f'{station_match.group(1)}-{station_match.group(2)}'
        elif train_num:
            item_name = train_num.group(1) + '次'
        elif any(x in text for x in ['火车票', '火车', '高铁', '动车']):
            item_name = '火车票'

    item_name = ' '.join(item_name.split()).strip()

    return {
        'invoice_number': invoice_number,
        'item_name': item_name,
        'total_amount': total_amount,
    }


def sanitize_filename(filename):
    """清理文件名中的非法字符。"""
    for ch in '\\/:*?"<>|':
        filename = filename.replace(ch, '_')
    return filename.rstrip(' .')
