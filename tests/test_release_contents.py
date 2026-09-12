"""Ensure the local release contains every imported application module and DLSS DLL."""
import ast
import hashlib
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    with zipfile.ZipFile(ROOT / 'neuralscreen-v1.7.0-full.zip') as archive:
        names = set(archive.namelist())
        queue, visited = ['main.py'], set()
        while queue:
            name = queue.pop()
            if name in visited:
                continue
            visited.add(name)
            assert name in names, f'Missing application module: {name}'
            expected = (ROOT / name).read_bytes().replace(b'\r\n', b'\n')
            assert archive.read(name).replace(b'\r\n', b'\n') == expected, f'Stale module: {name}'
            for node in ast.walk(ast.parse(expected)):
                imports = ([a.name for a in node.names] if isinstance(node, ast.Import)
                           else [node.module] if isinstance(node, ast.ImportFrom) and node.module else [])
                for module in imports:
                    child = module.split('.')[0] + '.py'
                    if (ROOT / child).is_file():
                        queue.append(child)
        manifest = archive.read('VERSION.txt').decode()
        for dll in ('nvngx_dlss.dll', 'nvngx_dlssg.dll', 'nvngx_dlssnr.dll'):
            name = 'native/' + dll
            digest = hashlib.sha256(archive.read(name)).hexdigest()
            assert digest in manifest, f'Missing or incorrect DLL hash: {dll}'
        assert not any(n.endswith(('.ready', '.part', '.bak', '.update.json')) for n in names)
        assert archive.testzip() is None, 'Invalid ZIP CRC'
    print(f'PASS: {len(visited)} application modules, three DLL hashes, ZIP CRC, no staged updates')


if __name__ == '__main__':
    main()
