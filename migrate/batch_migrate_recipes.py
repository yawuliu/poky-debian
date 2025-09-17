#!/usr/bin/env python3
"""
Yocto配方批量迁移工具
用于将所有在sources目录中有对应文件的配方从Poky层迁移到meta-debian层
"""

import os
import re
import shutil
import argparse
from pathlib import Path
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RecipeMigrator:
    def __init__(self, poky_path, meta_debian_path):
        self.poky_path = Path(poky_path)
        self.meta_debian_path = Path(meta_debian_path)
        self.migrated_recipes = []
        self.failed_recipes = []
        
    def get_all_recipe_names(self):
        """从sources目录获取所有配方名称"""
        sources_dir = self.meta_debian_path / "recipes-debian" / "sources"
        if not sources_dir.exists():
            logger.error(f"sources目录不存在: {sources_dir}")
            return []
        
        recipe_names = []
        for inc_file in sources_dir.glob("*.inc"):
            # 排除可能存在的特殊文件
            if inc_file.name.startswith("."):
                continue
                
            recipe_name = inc_file.stem
            recipe_names.append(recipe_name)
            
        logger.info(f"从sources目录找到 {len(recipe_names)} 个配方")
        return recipe_names
    
    def find_recipe_in_poky(self, recipe_name):
        """在Poky层中查找配方"""
        search_patterns = [
            f"**/recipes-*/{recipe_name}/{recipe_name}*.bb",
            f"**/recipes-*/{recipe_name}/*.bb",
            f"**/{recipe_name}*.bb"
        ]
        
        for pattern in search_patterns:
            for bb_file in self.poky_path.glob(pattern):
                return bb_file.parent
        
        return None
    
    def recipe_exists_in_debian(self, recipe_name):
        """检查配方是否已在meta-debian中存在"""
        target_dir = self.meta_debian_path / "recipes-debian" / recipe_name
        debian_bb_file = target_dir / f"{recipe_name}_debian.bb"
        return debian_bb_file.exists()
    
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
        try:
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
        except Exception as e:
            logger.error(f"解析bb文件失败: {bb_file}, 错误: {e}")
            return {}
    
    def create_debian_recipe(self, recipe_name, recipe_dir, files, bb_info):
        """创建Debian版本的配方"""
        # 创建目标目录
        target_dir = self.meta_debian_path / "recipes-debian" / recipe_name
        target_dir.mkdir(parents=True, exist_ok=True)
        
        # 复制所有相关文件
        for file_type, file_list in files.items():
            if file_type == 'bb_file':
                continue  # 我们会创建新的bb文件
            for file in file_list:
                try:
                    if file.is_dir():
                        shutil.copytree(file, target_dir / file.name, dirs_exist_ok=True)
                    else:
                        shutil.copy2(file, target_dir / file.name)
                except Exception as e:
                    logger.warning(f"复制文件失败: {file}, 错误: {e}")
        
        # 创建新的bb文件
        new_bb_content = self.generate_debian_bb_content(recipe_name, bb_info, files)
        new_bb_file = target_dir / f"{recipe_name}_debian.bb"
        
        try:
            with open(new_bb_file, 'w') as f:
                f.write(new_bb_content)
            
            logger.info(f"已创建Debian配方: {new_bb_file}")
            return new_bb_file
        except Exception as e:
            logger.error(f"创建bb文件失败: {new_bb_file}, 错误: {e}")
            return None
    
    def generate_debian_bb_content(self, recipe_name, bb_info, files):
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
        content.append(f'require recipes-debian/sources/{recipe_name}.inc')
        content.append('')
        
        # 添加原始inc文件的内容
        inc_files = files.get('inc_files', [])
        for inc_file in inc_files:
            content.append(f'require {inc_file.name}')
        content.append('')
        
        # 添加FILESPATH和SRC_URI
        corebase_path = os.path.relpath(self.poky_path, self.meta_debian_path)
        content.append(f'FILESPATH_append = ":${{COREBASE}}/{corebase_path}/meta/recipes-support/{recipe_name}/{recipe_name}"')
        
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
    
    def migrate_recipe(self, recipe_name):
        """迁移单个配方"""
        logger.info(f"开始迁移配方: {recipe_name}")
        
        # 检查配方是否已存在
        if self.recipe_exists_in_debian(recipe_name):
            logger.info(f"配方 {recipe_name} 已存在，跳过")
            return True
        
        # 查找Poky中的配方
        recipe_dir = self.find_recipe_in_poky(recipe_name)
        if not recipe_dir:
            logger.warning(f"在Poky中找不到配方 {recipe_name}")
            self.failed_recipes.append(recipe_name)
            return False
        
        logger.info(f"找到配方目录: {recipe_dir}")
        
        # 获取配方文件
        files = self.get_recipe_files(recipe_dir)
        if not files['bb_file']:
            logger.warning(f"在 {recipe_dir} 中找不到bb文件")
            self.failed_recipes.append(recipe_name)
            return False
        
        # 解析bb文件
        bb_info = self.parse_bb_file(files['bb_file'])
        if not bb_info:
            logger.warning(f"解析bb文件失败: {files['bb_file']}")
            self.failed_recipes.append(recipe_name)
            return False
        
        # 创建Debian配方
        new_bb_file = self.create_debian_recipe(recipe_name, recipe_dir, files, bb_info)
        if not new_bb_file:
            logger.warning(f"创建Debian配方失败: {recipe_name}")
            self.failed_recipes.append(recipe_name)
            return False
        
        logger.info(f"配方 {recipe_name} 迁移完成!")
        self.migrated_recipes.append(recipe_name)
        return True
    
    def migrate_all(self):
        """迁移所有配方"""
        recipe_names = self.get_all_recipe_names()
        if not recipe_names:
            logger.error("没有找到可迁移的配方")
            return False
        
        total = len(recipe_names)
        success_count = 0
        
        logger.info(f"开始批量迁移 {total} 个配方")
        
        for i, recipe_name in enumerate(recipe_names, 1):
            logger.info(f"处理配方 {i}/{total}: {recipe_name}")
            if self.migrate_recipe(recipe_name):
                success_count += 1
        
        # 输出迁移结果
        logger.info("=" * 50)
        logger.info(f"迁移完成! 成功: {success_count}/{total}")
        
        if self.failed_recipes:
            logger.info("失败的配方:")
            for recipe in self.failed_recipes:
                logger.info(f"  - {recipe}")
        
        return success_count > 0

def main():
    parser = argparse.ArgumentParser(description='批量迁移Yocto配方从Poky到meta-debian')
    parser.add_argument('--poky-path', default='../poky', help='Poky层路径 (默认: ../poky)')
    parser.add_argument('--meta-debian-path', default='.', help='meta-debian层路径 (默认: 当前目录)')
    parser.add_argument('--recipe', help='指定单个配方名称进行迁移（如果不指定，则迁移所有配方）')
    
    args = parser.parse_args()
    
    migrator = RecipeMigrator(args.poky_path, args.meta_debian_path)
    
    if args.recipe:
        # 迁移单个配方
        success = migrator.migrate_recipe(args.recipe)
        if not success:
            logger.error(f"配方 {args.recipe} 迁移失败!")
            return 1
        else:
            logger.info(f"配方 {args.recipe} 迁移成功!")
            return 0
    else:
        # 迁移所有配方
        success = migrator.migrate_all()
        if not success:
            logger.error("批量迁移失败!")
            return 1
        else:
            logger.info("批量迁移完成!")
            return 0

if __name__ == "__main__":
    exit(main())