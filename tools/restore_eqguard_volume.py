"""Restore one EqGuard archive and verify all restored research files."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import zipfile


def checksum(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('archive',type=Path)
    parser.add_argument('root',type=Path)
    parser.add_argument('sha256')
    args=parser.parse_args()
    assert checksum(args.archive)==args.sha256
    root=args.root.resolve()
    with zipfile.ZipFile(args.archive) as archive:
        manifest=json.loads(archive.read('_eqguard_volume_index.json'))
        expected={r['path']:r for r in manifest}
        assert len(expected)==len(manifest)
        assert len(archive.namelist())==len(expected)+1 and set(archive.namelist())==set(expected)|{'_eqguard_volume_index.json'}
        targets={}
        for name,row in expected.items():
            relative=PurePosixPath(name)
            assert name and not relative.is_absolute() and '..' not in relative.parts and '\\' not in name and ':' not in name
            assert archive.getinfo(name).file_size==row['bytes']
            dest=(root/name).resolve()
            assert dest.is_relative_to(root)
            if dest.exists():
                assert dest.is_file() and dest.stat().st_size==row['bytes'] and checksum(dest)==row['sha256'],name
            targets[name]=dest
        for name,dest in targets.items():
            if not dest.exists():
                dest.parent.mkdir(parents=True,exist_ok=True)
                with archive.open(name) as source,dest.open('xb') as output:
                    shutil.copyfileobj(source,output,1 << 20)
            assert dest.stat().st_size==expected[name]['bytes'] and checksum(dest)==expected[name]['sha256'],name
    print(f'Verified {len(targets)} restored files')


if __name__=='__main__':
    main()
