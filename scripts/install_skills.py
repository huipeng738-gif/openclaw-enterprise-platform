"""向已有企业插件部署两个试点 Skill；默认预检，--apply 才写入明确指定的目录。"""
import argparse
import json
import os
from pathlib import Path
import tempfile

from verify_skills import ROOT, SKILLS, check_package


def install(plugin_dir, apply=False):
    """只新增 Skill 文件及 manifest 的 skills 声明，遇到不同版本文件时停止。"""
    check_package()
    target_root = plugin_dir.resolve(strict=True)
    manifest_path = target_root / 'openclaw.plugin.json'
    if manifest_path.is_symlink():
        raise RuntimeError('拒绝修改符号链接 manifest')
    original = manifest_path.read_bytes()
    manifest = json.loads(original)
    if manifest.get('id') != 'enterprise-data-tools':
        raise RuntimeError('目标目录不是 enterprise-data-tools 插件')
    roots = manifest.get('skills', [])
    if not isinstance(roots, list):
        raise RuntimeError('目标 manifest 的 skills 字段必须为数组')
    pending = []
    for name in SKILLS:
        source_root = ROOT / 'plugin/skills' / name
        for source in source_root.rglob('*'):
            if not source.is_file():
                continue
            destination = target_root / 'skills' / name / source.relative_to(source_root)
            if not destination.resolve().is_relative_to(target_root):
                raise RuntimeError('目标 Skill 路径超出插件目录')
            if destination.is_symlink():
                raise RuntimeError('拒绝覆盖符号链接 Skill 文件')
            if destination.exists():
                if destination.read_bytes() != source.read_bytes():
                    raise RuntimeError(f'{name}: 目标文件已有不同内容，请人工审核后合并')
            else:
                pending.append((source, destination))
    backup = target_root / 'openclaw.plugin.before-skills.json'
    change_manifest = './skills' not in roots
    if change_manifest and backup.exists() and backup.read_bytes() != original:
        raise RuntimeError('已存在不同内容的 manifest 备份，停止以免覆盖')
    print(f'预检通过：新增 {len(pending)} 个文件；更新 manifest: {change_manifest}')
    if not apply:
        print('未写入；使用 --apply 执行部署。')
        return
    for source, destination in pending:
        destination.parent.mkdir(parents=True, exist_ok=True)
        # 排他创建避免覆盖预检后其他进程新增的文件。
        with destination.open('xb') as output:
            output.write(source.read_bytes())
    if change_manifest:
        if manifest_path.read_bytes() != original:
            raise RuntimeError('manifest 在预检后发生变化，停止更新；新增 Skill 文件尚未声明')
        if not backup.exists():
            with backup.open('xb') as output:
                output.write(original)
        manifest['skills'] = [*roots, './skills']
        with tempfile.NamedTemporaryFile(dir=target_root, delete=False) as output:
            temporary = Path(output.name)
            output.write((json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
        try:
            os.replace(temporary, manifest_path)
        finally:
            temporary.unlink(missing_ok=True)
    print('部署完成：保留已有 Tool、插件配置和 Agent 权限；请执行 --runtime 加载检查。')


def main():
    """要求明确插件目录，不自动寻找或修改 Gateway 全局配置。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plugin-dir', required=True, type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    try:
        install(args.plugin_dir, args.apply)
    except (RuntimeError, OSError, ValueError) as exc:
        print(f'FAIL: {exc}' if isinstance(exc, RuntimeError) else f'FAIL: {type(exc).__name__}')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
