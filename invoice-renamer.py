import os
import sys

try:
    from pypdf import PdfReader
except ImportError:
    print("错误: 需要安装 pypdf 库")
    print("请运行: pip install pypdf")
    sys.exit(1)

from invoice_parser import extract_invoice_info, sanitize_filename, setup_console


def process_invoice_pdf(file_path, dry_run=False):
    """处理单个发票PDF文件"""
    try:
        reader = PdfReader(file_path)
        full_text = ''

        for page in reader.pages:
            text = page.extract_text()
            if text:
                full_text += text + ' '

        if not full_text.strip():
            print("  ❌ 无法提取文本")
            return {'success': False, 'reason': '无法提取文本'}

        info = extract_invoice_info(full_text)

        print(f"\n文件: {os.path.basename(file_path)}")
        print(f"  发票号码: {info['invoice_number'] or '未找到'}")
        print(f"  项目名称: {info['item_name'] or '未找到'}")
        print(f"  价税合计: {info['total_amount'] or '未找到'}")

        if not info['invoice_number']:
            print("  ⚠️  无法提取发票号码，跳过重命名")
            return {'success': False, 'reason': '无法提取发票号码'}

        ext = os.path.splitext(file_path)[1]
        new_name = f"{info['invoice_number']}_{info['item_name'] or '未知项目'}_{info['total_amount'] or '0'}{ext}"
        new_path = os.path.join(os.path.dirname(file_path), sanitize_filename(new_name))

        if new_path == file_path:
            print("  ℹ️  文件名无需更改")
            return {'success': True, 'unchanged': True}

        if dry_run:
            print(f"  ✅ 将重命名为: {os.path.basename(new_path)}")
            return {'success': True, 'new_path': new_path}

        if os.path.exists(new_path):
            print(f"  ⚠️  目标文件已存在: {os.path.basename(new_path)}")
            base, ext = os.path.splitext(new_path)
            counter = 1
            while os.path.exists(f"{base}_{counter}{ext}") and counter < 100:
                counter += 1
            new_path = f"{base}_{counter}{ext}"

        os.rename(file_path, new_path)
        print(f"  ✅ 已重命名为: {os.path.basename(new_path)}")
        return {'success': True, 'new_path': new_path}

    except Exception as e:
        print(f"  ❌ 处理失败: {e}")
        return {'success': False, 'reason': str(e)}


def process_directory(dir_path, dry_run=False):
    """处理目录中的所有PDF文件"""
    if not os.path.exists(dir_path):
        print(f"错误: 目录不存在: {dir_path}")
        sys.exit(1)

    files = [os.path.join(dir_path, f) for f in os.listdir(dir_path)
             if f.lower().endswith('.pdf')]

    if not files:
        print('目录中没有找到PDF文件')
        return

    print(f"找到 {len(files)} 个PDF文件{' (预览模式)' if dry_run else ''}")
    print('=' * 50)

    success_count = 0
    fail_count = 0

    for file_path in files:
        result = process_invoice_pdf(file_path, dry_run)
        if result['success']:
            success_count += 1
        else:
            fail_count += 1

    print('=' * 50)
    print(f"处理完成: 成功 {success_count}, 失败 {fail_count}")


if __name__ == '__main__':
    setup_console()

    if len(sys.argv) == 1:
        print('''
发票PDF批量重命名工具

用法: python invoice-renamer.py <目录路径> [--dry-run]

参数:
  <目录路径>   包含发票PDF文件的目录路径
  --dry-run   预览模式，只显示信息不实际重命名

示例:
  python invoice-renamer.py .
  python invoice-renamer.py D:\\发票
  python invoice-renamer.py ./invoices --dry-run
''')
        sys.exit(0)

    dir_path = sys.argv[1]
    dry_run = '--dry-run' in sys.argv

    if dry_run:
        print('⚠️  预览模式: 不会实际重命名文件\n')

    process_directory(dir_path, dry_run)
