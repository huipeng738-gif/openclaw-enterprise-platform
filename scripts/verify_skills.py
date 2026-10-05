"""检查项目 Skill 包；--runtime 只读检查指定 Agent 的实际加载情况。"""
import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ('enterprise-knowledge-qa', 'enterprise-document-draft')


def check_package(root=ROOT):
    """检查 manifest 声明、Skill 元数据及本地模板引用，不加载运行时代码。"""
    plugin = root / 'plugin'
    manifest = json.loads((plugin / 'openclaw.plugin.json').read_text(encoding='utf-8'))
    if './skills' not in manifest.get('skills', []):
        raise RuntimeError('插件 manifest 未声明 ./skills')
    for name in SKILLS:
        directory = plugin / 'skills' / name
        text = (directory / 'SKILL.md').read_text(encoding='utf-8')
        match = re.match(r'\A---\r?\n(.*?)\r?\n---\r?\n', text, re.S)
        if not match:
            raise RuntimeError(f'{name}: 缺少 YAML frontmatter')
        fields = dict(re.findall(r'^(name|description|metadata): (.+)$', match[1], re.M))
        if fields.get('name') != name or not fields.get('description'):
            raise RuntimeError(f'{name}: 名称或描述无效')
        metadata = json.loads(fields['metadata'])
        if metadata['openclaw']['requires']['config'] != ['plugins.entries.enterprise-data-tools.enabled']:
            raise RuntimeError(f'{name}: 插件启用条件无效')
        for reference in re.findall(r'\{baseDir\}/([\w./-]+)', text):
            target = (directory / reference).resolve()
            if not target.is_relative_to(directory.resolve()) or not target.is_file():
                raise RuntimeError(f'{name}: 模板引用不存在或超出 Skill 目录')
        print(f'PASS package: {name}')


def cli_json(executable, *args):
    """捕获 CLI 输出，只解析 JSON；不打印可能包含配置或凭据的原始错误。"""
    result = subprocess.run([executable, *args, '--json'], capture_output=True, text=True,
                            encoding='utf-8', timeout=45, check=False)
    if result.returncode:
        raise RuntimeError(f'OpenClaw {args[0]} 检查失败（退出码 {result.returncode}），未输出原始配置')
    try:
        return json.loads(result.stdout)
    except ValueError as exc:
        raise RuntimeError('OpenClaw 未返回纯 JSON；请在 Gateway 主机检查 CLI 版本与诊断信息') from exc


def check_runtime(agent, executable):
    """确认 Agent workspace 和两个 Skill 的可用状态，不发送 Agent 任务。"""
    agents = cli_json(executable, 'agents', 'list')
    selected = next((item for item in agents if item.get('id') == agent), None)
    if selected is None:
        raise RuntimeError('指定 Agent 不存在')
    print(f'Agent: {agent}; workspace: {selected.get("workspace", "unknown")}')
    for name in SKILLS:
        info = cli_json(executable, 'skills', 'info', name, '--agent', agent)
        if info.get('name') != name or info.get('eligible') is not True:
            raise RuntimeError(f'{name}: 对指定 Agent 不可用；检查插件启用、Skill allowlist 和依赖')
        # 同名 workspace Skill 优先级更高，不能把它误认为项目插件已部署。
        skill_path = Path(info.get('filePath', ''))
        if not skill_path.is_file() or skill_path.read_bytes() != (ROOT / 'plugin/skills' / name / 'SKILL.md').read_bytes():
            raise RuntimeError(f'{name}: 实际加载的 Skill 与项目版本不一致')
        print(f'PASS runtime: {name}')
    print('加载检查完成；Tool 权限、服务连通性和模型行为仍需实际任务验收。')


def show_environment(executable):
    """只展示版本、插件位置与工具策略，过滤模型配置和凭据字段。"""
    version = subprocess.run([executable, '--version'], capture_output=True, text=True,
                             encoding='utf-8', timeout=45, check=True)
    match = re.search(r'\d{4}\.\d+\.\d+', version.stdout)
    print('OpenClaw version:', match[0] if match else 'unknown')
    inspection = cli_json(executable, 'plugins', 'inspect', 'enterprise-data-tools')
    plugin = inspection.get('plugin', inspection)
    for field in ('id', 'status', 'source', 'rootDir', 'toolNames', 'skills'):
        if field in plugin:
            print(f'Plugin {field}: {json.dumps(plugin[field], ensure_ascii=False)}')
    enabled = cli_json(executable, 'config', 'get', 'plugins.entries.enterprise-data-tools.enabled')
    print('Plugin enabled:', enabled is True)
    listing = cli_json(executable, 'skills', 'list', '--agent', 'coordinator')
    visible = listing.get('skills', []) if isinstance(listing, dict) else listing
    print('Discovered project skills:', json.dumps([
        {key: item[key] for key in ('name', 'eligible', 'source') if key in item}
        for item in visible if item.get('name') in SKILLS], ensure_ascii=False))
    agents = cli_json(executable, 'config', 'get', 'agents')
    global_tools = cli_json(executable, 'config', 'get', 'tools')
    print('Global tools:', json.dumps({key: global_tools[key] for key in ('profile', 'allow', 'alsoAllow', 'deny')
                                      if key in global_tools}, ensure_ascii=False))
    # 兼容旧版 list 与新版 entries 配置；只打印工具策略及 Skill allowlist。
    defaults = agents.get('defaults', {})
    print('Default skills:', json.dumps(defaults.get('skills', 'unrestricted'), ensure_ascii=False))
    entries = agents.get('list', [])
    if isinstance(agents.get('entries'), dict):
        entries = [dict(value, id=key) for key, value in agents['entries'].items()]
    for entry in entries:
        tools = entry.get('tools', {})
        print(json.dumps({'agent': entry.get('id'), 'skills': entry.get('skills', 'inherit'),
                          'tools': {key: tools[key] for key in ('profile', 'allow', 'alsoAllow', 'deny') if key in tools}},
                         ensure_ascii=False))


def main():
    """默认只检查仓库文件；显式 --runtime 才调用本机 OpenClaw。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', action='store_true')
    parser.add_argument('--environment', action='store_true', help='只读输出版本、插件位置和 Agent 策略')
    parser.add_argument('--agent', default='coordinator')
    parser.add_argument('--openclaw', default='openclaw')
    args = parser.parse_args()
    try:
        check_package()
        if args.runtime or args.environment:
            executable = shutil.which(args.openclaw)
            if not executable:
                raise RuntimeError('当前 PATH 中未找到 OpenClaw；请在 Gateway 主机执行运行时检查')
            if args.environment:
                show_environment(executable)
            if args.runtime:
                check_runtime(args.agent, executable)
    except (RuntimeError, OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print(f'FAIL: {exc}' if isinstance(exc, RuntimeError) else f'FAIL: {type(exc).__name__}')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
