#!/usr/bin/env python3
"""
Yocto配方迁移工具
用于将配方从Poky层迁移到meta-debian层
"""

import os
import re
import shutil
import argparse
from pathlib import Path

class RecipeMigrator:
    def __init__(self, poky_path, meta_debian_path, recipe_name):
        self.poky_path = Path(poky_path)
        self.meta_debian_path = Path(meta_debian_path)
        self.recipe_name = recipe_name
        self.debian_recipe_name = f"{recipe_name}_debian"
        
    def find_recipe_in_poky(self):
        """在Poky层中查找配方"""
        search_patterns = [
            f"**/recipes-*/{self.recipe_name}/{self.recipe_name}*.bb",
            f"**/recipes-*/{self.recipe_name}/*.bb",
            f"**/{self.recipe_name}*.bb"
        ]
        
        for pattern in search_patterns:
            for bb_file in self.poky_path.glob(pattern):
                return bb_file.parent
        
        return None
    
    def get_recipe_files(self, recipe_dir):
        """获取配方相关的所有文件"""
        files = {
            'bb_file': None,
            'inc_files': [],
            'patch_files': [],
            'other_files': []
        }
        
        for file in recipe_dir.iterdir():
            if file.suffix == '.bb':
                files['bb_file'] = file
            elif file.suffix == '.inc':
                files['inc_files'].append(file)
            elif file.suffix == '.patch' or file.name == 'files':
                files['patch_files'].append(file)
            else:
                files['other_files'].append(file)
                
        return files
    
    def parse_bb_file(self, bb_file):
        """解析bb文件内容"""
        with open(bb_file, 'r') as f:
            content = f.read()
        
        # 提取LICENSE和LIC_FILES_CHKSUM
        license_match = re.search(r'^LICENSE\s*[?+]?=\s*["\']?(.*?)["\']?\s*$', content, re.MULTILINE)
        lic_files_chksum_match = re.search(r'^LIC_FILES_CHKSUM\s*[?+]?=\s*["\']?(.*?)["\']?\s*$', content, re.MULTILINE)
        
        # 提取SRC_URI
        src_uri_match = re.search(r'^SRC_URI\s*[?+]?=\s*["\']?(.*?)["\']?\s*$', content, re.MULTILINE)
        
        # 提取S变量
        s_var_match = re.search(r'^S\s*[?+]?=\s*["\']?(.*?)["\']?\s*$', content, re.MULTILINE)
        
        return {
            'license': license_match.group(1) if license_match else None,
            'lic_files_chksum': lic_files_chksum_match.group(1) if lic_files_chksum_match else None,
            'src_uri': src_uri_match.group(1) if src_uri_match else None,
            's_var': s_var_match.group(1) if s_var_match else None,
            'content': content
        }
    
    def create_debian_recipe(self, recipe_dir, files, bb_info):
        """创建Debian版本的配方"""
        # 创建目标目录
        target_dir = self.meta_debian_path / "recipes-debian" / self.recipe_name
        target_dir.mkdir(parents=True, exist_ok=True)
        
        # 复制所有相关文件
        for file_type, file_list in files.items():
            if file_type == 'bb_file':
                continue  # 我们会创建新的bb文件
            for file in file_list:
                if file.is_dir():
                    shutil.copytree(file, target_dir / file.name, dirs_exist_ok=True)
                else:
                    shutil.copy2(file, target_dir / file.name)
        
        # 创建新的bb文件
        new_bb_content = self.generate_debian_bb_content(bb_info, files)
        new_bb_file = target_dir / f"{self.debian_recipe_name}.bb"
        
        with open(new_bb_file, 'w') as f:
            f.write(new_bb_content)
        
        print(f"已创建Debian配方: {new_bb_file}")
        
        # 创建sources文件
        self.create_sources_file()
        
        return new_bb_file
    
    def generate_debian_bb_content(self, bb_info, files):
        """生成Debian版本的bb文件内容"""
        content = []
        
        # 添加LICENSE和LIC_FILES_CHKSUM
        license = bb_info.get('license', 'Unknown')
        lic_files_chksum = bb_info.get('lic_files_chksum', '')
        
        # 调整LIC_FILES_CHKSUM路径（如果S变量被修改）
        if lic_files_chksum and '${S}' in lic_files_chksum and bb_info.get('s_var'):
            # 如果S变量被修改，可能需要调整LIC_FILES_CHKSUM路径
            lic_files_chksum = lic_files_chksum.replace('${S}', '..')
        
        content.append(f'LICENSE = "{license}"')
        content.append(f'LIC_FILES_CHKSUM = "{lic_files_chksum}"')
        content.append('')
        
        # 添加继承和包含
        content.append('inherit debian-package')
        content.append(f'require recipes-debian/sources/{self.recipe_name}.inc')
        content.append('')
        
        # 添加原始inc文件的内容
        inc_files = files.get('inc_files', [])
        for inc_file in inc_files:
            content.append(f'require {inc_file.name}')
        content.append('')
        
        # 添加FILESPATH和SRC_URI
        corebase_path = os.path.relpath(self.poky_path, self.meta_debian_path)
        content.append(f'FILESPATH_append = ":${{COREBASE}}/{corebase_path}/meta/recipes-support/{self.recipe_name}/{self.recipe_name}"')
        
        # 添加补丁文件到SRC_URI
        patch_files = files.get('patch_files', [])
        if patch_files:
            patch_uris = []
            for patch_file in patch_files:
                if patch_file.suffix == '.patch':
                    patch_uris.append(f'file://{patch_file.name}')
            
            if patch_uris:
                content.append(f'SRC_URI += "{", ".join(patch_uris)}"')
                content.append('')
        
        # 添加S变量（如果需要）
        if bb_info.get('s_var'):
            content.append(f'S = "${{DEBIAN_UNPACK_DIR}}/{bb_info["s_var"]}"')
        
        return '\n'.join(content)
    
    def create_sources_file(self):
        """创建sources文件"""
        sources_dir = self.meta_debian_path / "recipes-debian" / "sources"
        sources_dir.mkdir(parents=True, exist_ok=True)
        
        sources_file = sources_dir / f"{self.recipe_name}.inc"
        if not sources_file.exists():
            with open(sources_file, 'w') as f:
                f.write(f"# Debian source information for {self.recipe_name}\n")
                f.write(f"DEBIAN_SRC_{self.recipe_name.upper()} ?= \"debian\"\n")
            
            print(f"已创建sources文件: {sources_file}")
    
    def migrate(self):
        """执行迁移过程"""
        print(f"开始迁移配方: {self.recipe_name}")
        
        # 查找Poky中的配方
        recipe_dir = self.find_recipe_in_poky()
        if not recipe_dir:
            print(f"错误: 在Poky中找不到配方 {self.recipe_name}")
            return False
        
        print(f"找到配方目录: {recipe_dir}")
        
        # 获取配方文件
        files = self.get_recipe_files(recipe_dir)
        if not files['bb_file']:
            print(f"错误: 在 {recipe_dir} 中找不到bb文件")
            return False
        
        # 解析bb文件
        bb_info = self.parse_bb_file(files['bb_file'])
        
        # 创建Debian配方
        new_bb_file = self.create_debian_recipe(recipe_dir, files, bb_info)
        
        print(f"配方 {self.recipe_name} 迁移完成!")
        return True

def main():
    parser = argparse.ArgumentParser(description='迁移Yocto配方从Poky到meta-debian')
    parser.add_argument('recipe_name', help='要迁移的配方名称')
    parser.add_argument('--poky-path', default='../poky', help='Poky层路径 (默认: ../poky)')
    parser.add_argument('--meta-debian-path', default='.', help='meta-debian层路径 (默认: 当前目录)')
    
    args = parser.parse_args()
    
    migrator = RecipeMigrator(args.poky_path, args.meta_debian_path, args.recipe_name)
    success = migrator.migrate()
    
    if not success:
        print("迁移失败!")
        return 1
    
    print("迁移成功!")
    return 0

if __name__ == "__main__":
    exit(main())