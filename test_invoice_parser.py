"""发票解析回归测试。

用法:
    python test_invoice_parser.py

测试内容:
1. 中文大写金额解析（纯函数，无需 PDF）
2. 文件名清理
3. 典型版式文本片段（不依赖本地 PDF，防止回归）
4. 本目录真实发票 PDF 端到端校验（文件不存在则跳过）
"""
import glob
import os
import sys

from pypdf import PdfReader

from invoice_parser import extract_invoice_info, parse_cn_amount, sanitize_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 发票号码 -> (项目名称, 价税合计)
EXPECTED = {
    '26317000004179235757': ('生产生活服务*餐饮服务', '74.80'),
    '26317000004186967640': ('生产生活服务*餐饮服务', '149.90'),
    '26317000004277849609': ('生产生活服务*物流网络', '6.40'),
    '26327000001902228052': ('汽油*95号车用汽油', '244.82'),
    '26327000001905874268': ('生产生活服务*餐饮服务', '118.80'),
    '26327000001979894373': ('生产生活服务*餐饮服务', '45.00'),
    '26332000009959830381': ('生产生活服务*旅游服务', '757.00'),
    '26347000000249593790': ('乙醇汽油*95#车用乙醇', '296.60'),
    '26347000000249594784': ('乙醇汽油*95#车用乙醇', '377.54'),
    '26347000000249595817': ('乙醇汽油*95#车用乙醇', '363.98'),
    '26347000000249597744': ('乙醇汽油*95#车用乙醇', '390.36'),
    '26347000000249598822': ('乙醇汽油*95#车用乙醇', '301.56'),
    '26347000000249600557': ('乙醇汽油*95#车用乙醇', '277.49'),
}

CN_AMOUNT_CASES = [
    ('贰佰零陆圆整', '206.00'),
    ('捌佰玖拾玖圆整', '899.00'),
    ('叁佰叁拾圆整', '330.00'),
    ('壹佰壹拾玖圆玖角', '119.90'),
    ('壹仟捌佰伍拾玖圆整', '1859.00'),
    ('柒佰伍拾捌圆伍角整', '758.50'),
    ('肆拾柒圆伍角整', '47.50'),
    ('柒拾玖圆零叁分', '79.03'),
    ('贰佰肆拾叁圆壹角整', '243.10'),
    ('壹佰壹拾捌元捌角', '118.80'),
    ('柒拾肆元捌角', '74.80'),
    ('贰佰肆拾肆圆捌角贰分', '244.82'),
    ('壹万零伍佰圆整', '10500.00'),
    ('壹佰贰拾叁万肆仟伍佰陆拾柒圆捌角玖分', '1234567.89'),
]

# 典型版式片段：(说明, 文本, 期望项目名称, 期望价税合计)
TEXT_CASES = [
    (
        # "（小写）"后面先出现的是合计金额，真正的价税合计在后面
        '小写标签后紧跟合计金额',
        '发票号码：26332000007401077821\n'
        '合 计\n'
        '价税合计（大写） （小写）\n'
        '备\n注\n开票人：\n'
        '¥326.73 ¥3.27\n'
        '叁佰叁拾圆整 ¥ 330.00\n'
        '*生产生活服务*餐饮 326.73 1% 3.27',
        '生产生活服务*餐饮',
        '330.00',
    ),
    (
        # 金额列里有"政府补贴"，价税合计仍以大写为准
        '多行品名 + 补贴金额',
        '发票号码：26952000004069549426\n'
        '价税合计（大写） （小写）\n'
        '¥ 215.14 ¥ 27.96\n'
        '贰佰肆拾叁圆壹角整 ¥ 243.10\n'
        '*公共安全设备*乔安摄像\n'
        '头门口免插电无线太阳能\n'
        '监控家用远程无需网络室\n'
        '内外高清\n'
        'ZH0G4S7LLBJXHK\n'
        '13%个 253.10 32.90\n'
        '淘宝订单号:5127758965001283326;政府补贴金额:42.90元;实付金额:243.10元',
        '公共安全设备*乔安摄像头门口免插电无线太阳能监控家用远程无需网络室内外高清',
        '243.10',
    ),
    (
        # 品名跨行被切断：usb风 + 扇
        '品名跨行拼接',
        '发票号码：26952000002596701076\n'
        '*家用通风电器具*usb风\n'
        '扇\n'
        '1%78.25 0.78\n'
        '柒拾玖圆零叁分 ¥ 79.03',
        '家用通风电器具*usb风扇',
        '79.03',
    ),
    (
        # 30 字硬截断曾把 "Wi-Fi" 切成 "Wi-"
        '长品名按词边界截断',
        '发票号码：26337000000644181799\n'
        '*计算机网络设备*普联（TP-LINK）AX1500双频Wi-Fi 6无线路由\n'
        '器 5G双频 百兆 易展Mesh\n'
        'TL-XDR1500 台 1 106.11 106.11 13.79 13%\n'
        '¥106.11 ¥13.79\n'
        '壹佰壹拾玖圆玖角 ¥119.90',
        '计算机网络设备*普联(TP-LINK)AX1500双频Wi-Fi',
        '119.90',
    ),
    (
        # 部分 PDF 把汉字输出成部首字符（⻆ U+2EC6），曾导致 118.80 被识别成 118.00
        '部首字符归一化',
        '发票号码：26327000001905874268\n'
        '2026年11⽉16⽇\n'
        '上海海思拓汽⻋电⼦有限公司 ⽆锡⾦拱⻔⻝品有限公司\n'
        '112.08¥ 6.72¥\n'
        '118.80¥壹佰壹拾捌元捌⻆\n'
        '*⽣产⽣活服务*餐饮服务 1.0 112.08 112.08 6% 6.72',
        '生产生活服务*餐饮服务',
        '118.80',
    ),
]


def test_cn_amount():
    failures = []
    for text, expected in CN_AMOUNT_CASES:
        actual = parse_cn_amount(text)
        if actual != expected:
            failures.append(f'  {text}: 期望 {expected}, 实际 {actual}')
    return failures


def test_sanitize_filename():
    failures = []
    cases = [
        ('a*b?c.pdf', 'a_b_c.pdf'),
        ('a/b\\c.pdf', 'a_b_c.pdf'),
        ('name.pdf ', 'name.pdf'),
    ]
    for raw, expected in cases:
        actual = sanitize_filename(raw)
        if actual != expected:
            failures.append(f'  {raw!r}: 期望 {expected!r}, 实际 {actual!r}')
    return failures


def test_text_cases():
    failures = []
    for label, text, expected_name, expected_amount in TEXT_CASES:
        info = extract_invoice_info(text)
        if info['item_name'] != expected_name:
            failures.append(f'  [{label}] 项目名称 期望 {expected_name!r}, 实际 {info["item_name"]!r}')
        if info['total_amount'] != expected_amount:
            failures.append(f'  [{label}] 价税合计 期望 {expected_amount}, 实际 {info["total_amount"]}')
    return failures


def test_real_invoices():
    failures = []
    checked = 0
    skipped = 0
    for number, (expected_name, expected_amount) in EXPECTED.items():
        paths = glob.glob(os.path.join(BASE_DIR, f'{number}*.pdf'))
        if not paths:
            skipped += 1
            continue
        checked += 1
        text = ''
        for page in PdfReader(paths[0]).pages:
            text += (page.extract_text() or '') + ' '
        info = extract_invoice_info(text)
        if info['invoice_number'] != number:
            failures.append(f'  {number}: 发票号码识别为 {info["invoice_number"]!r}')
        if info['item_name'] != expected_name:
            failures.append(f'  {number}: 项目名称 期望 {expected_name!r}, 实际 {info["item_name"]!r}')
        if info['total_amount'] != expected_amount:
            failures.append(f'  {number}: 价税合计 期望 {expected_amount}, 实际 {info["total_amount"]}')
    return failures, checked, skipped


def main():
    failed = 0

    for label, failures, extra in (
        ('中文大写金额解析', test_cn_amount(), f'{len(CN_AMOUNT_CASES)} 例'),
        ('文件名清理', test_sanitize_filename(), ''),
        ('典型版式片段', test_text_cases(), f'{len(TEXT_CASES)} 例'),
    ):
        failed += len(failures)
        print(f'[{"OK" if not failures else "FAIL"}] {label}' + (f' ({extra})' if extra else ''))
        for line in failures:
            print(line)

    failures, checked, skipped = test_real_invoices()
    failed += len(failures)
    print(f'[{"OK" if not failures else "FAIL"}] 真实发票识别 (校验 {checked} 张, 跳过 {skipped} 张)')
    for line in failures:
        print(line)

    print()
    if failed:
        print(f'失败 {failed} 项')
        sys.exit(1)
    print('全部通过')


if __name__ == '__main__':
    main()
