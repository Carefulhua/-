"""发票解析回归测试。

用法:
    python test_invoice_parser.py

测试内容:
1. 中文大写金额解析（纯函数，无需 PDF）
2. 对本目录下的真实发票 PDF 做端到端校验（文件不存在则跳过该用例）
"""
import glob
import os
import sys

from pypdf import PdfReader

from invoice_parser import extract_invoice_info, parse_cn_amount, sanitize_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 发票号码 -> (项目名称, 价税合计)
EXPECTED = {
    '26312000006250130881': ('生产生活服务*餐饮服务', '206.00'),
    '26322000008202517261': ('生产生活服务*住宿费', '899.00'),
    '26332000007401077821': ('生产生活服务*餐饮', '330.00'),
    '26337000000644181799': ('计算机网络设备*普联（TP-LINK）AX1500双频Wi-Fi', '119.90'),
    '26342000003150964246': ('生产生活服务*餐饮费', '1859.00'),
    '26342000003152486146': ('生产生活服务*餐饮费', '758.50'),
    '26442000008578317196': ('印刷品*制作费', '47.50'),
    '26952000002596701076': ('家用通风电器具*usb风扇', '79.03'),
    '26952000004069549426': (
        '公共安全设备*乔安摄像头门口免插电无线太阳能监控家用远程无需网络室内外高清',
        '243.10',
    ),
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
    ('壹万零伍佰圆整', '10500.00'),
    ('壹佰贰拾叁万肆仟伍佰陆拾柒圆捌角玖分', '1234567.89'),
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

    failures = test_cn_amount()
    failed += len(failures)
    print(f'[{"OK" if not failures else "FAIL"}] 中文大写金额解析 ({len(CN_AMOUNT_CASES)} 例)')
    for line in failures:
        print(line)

    failures = test_sanitize_filename()
    failed += len(failures)
    print(f'[{"OK" if not failures else "FAIL"}] 文件名清理')
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
