"""修复长路径复制 86 个不完整文件夹"""
import os, sys, io, shutil
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

PREFIX = "\\\\?\\"

def long_path(path):
    abs_path = os.path.abspath(path)
    if os.name == 'nt' and not abs_path.startswith(PREFIX):
        return PREFIX + abs_path
    return abs_path

src = 'd:/CeramiKG/pdf-flask-handler/uploads/new207/mineru_results'
dst = 'd:/CeramiKG/pdf-flask-handler/uploads/247'

# Find incomplete folders (no md files)
incomplete = []
for d in os.listdir(dst):
    dp = os.path.join(dst, d)
    if not os.path.isdir(dp):
        continue
    has_md = any(f.endswith('.md') for f in os.listdir(dp))
    if not has_md:
        incomplete.append(d)

print(f'待修复: {len(incomplete)} 个不完整文件夹')

fixed = 0
for i, d in enumerate(incomplete):
    src_dir = os.path.join(src, d)
    dst_dir = os.path.join(dst, d)

    if not os.path.isdir(src_dir):
        print(f'  [{i+1}/{len(incomplete)}] 源不存在: {d[:60]}')
        continue

    # Remove incomplete destination
    try:
        shutil.rmtree(long_path(dst_dir))
    except:
        pass

    # Copy using long path
    try:
        shutil.copytree(long_path(src_dir), long_path(dst_dir))
        fixed += 1
    except Exception as e:
        # Manual file-by-file copy
        try:
            os.makedirs(long_path(dst_dir), exist_ok=True)
            for f in os.listdir(long_path(src_dir)):
                sf = long_path(os.path.join(src_dir, f))
                df = long_path(os.path.join(dst_dir, f))
                try:
                    if os.path.isfile(sf):
                        shutil.copy2(sf, df)
                    else:
                        shutil.copytree(sf, df)
                except:
                    pass
            fixed += 1
        except Exception as e2:
            print(f'  FAIL [{i+1}]: {d[:50]}...')

    if (i + 1) % 30 == 0:
        print(f'  进度: {i+1}/{len(incomplete)}')

# Re-check
still_bad = 0
for d in incomplete:
    dp = os.path.join(dst, d)
    if os.path.isdir(dp):
        has_md = any(f.endswith('.md') for f in os.listdir(dp))
        if not has_md:
            still_bad += 1

print(f'修复: {fixed}/{len(incomplete)}, 仍有问题: {still_bad}')
