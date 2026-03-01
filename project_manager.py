#!/usr/bin/env python3
"""
项目管理器 - 管理多个项目目录的快速切换
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict


@dataclass
class Project:
    """项目定义"""
    name: str           # 项目名称（唯一标识）
    path: str           # 项目路径
    alias: List[str]    # 别名列表
    description: str    # 项目描述


class ProjectManager:
    """项目管理器"""

    def __init__(self, config_path: str = None):
        """
        初始化项目管理器

        Args:
            config_path: 配置文件路径，默认为 ~/.claude/projects.json
        """
        if config_path is None:
            config_dir = os.path.expanduser("~/.claude")
            os.makedirs(config_dir, exist_ok=True)
            config_path = os.path.join(config_dir, "projects.json")

        self.config_path = config_path
        self.projects: Dict[str, Project] = {}
        self.load()

    def load(self):
        """从配置文件加载项目"""
        if not os.path.exists(self.config_path):
            # 创建默认配置
            self._create_default_config()
            return

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            projects_data = data.get('projects', {})
            for name, proj_data in projects_data.items():
                self.projects[name] = Project(
                    name=name,
                    path=proj_data['path'],
                    alias=proj_data.get('alias', []),
                    description=proj_data.get('description', '')
                )
        except Exception as e:
            print(f"[警告] 加载项目配置失败: {e}")
            self._create_default_config()

    def save(self):
        """保存项目到配置文件"""
        data = {
            'projects': {
                name: {
                    'path': proj.path,
                    'alias': proj.alias,
                    'description': proj.description
                }
                for name, proj in self.projects.items()
            }
        }

        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _create_default_config(self):
        """创建默认配置"""
        # 自动扫描 ~/projects 目录下的项目
        projects_dir = os.path.expanduser("~/projects")
        if os.path.isdir(projects_dir):
            for item in os.listdir(projects_dir):
                item_path = os.path.join(projects_dir, item)
                if os.path.isdir(item_path):
                    # 检查是否是一个项目目录（包含 .git 或常见项目文件）
                    is_project = (
                        os.path.exists(os.path.join(item_path, '.git')) or
                        os.path.exists(os.path.join(item_path, 'package.json')) or
                        os.path.exists(os.path.join(item_path, 'pyproject.toml')) or
                        os.path.exists(os.path.join(item_path, 'Cargo.toml')) or
                        os.path.exists(os.path.join(item_path, 'go.mod'))
                    )

                    if is_project:
                        # 生成简短别名
                        alias = self._generate_alias(item)
                        self.projects[item] = Project(
                            name=item,
                            path=item_path,
                            alias=alias,
                            description=f"项目: {item}"
                        )

        self.save()

    def _generate_alias(self, name: str) -> List[str]:
        """生成项目别名"""
        alias = []
        words = name.replace('-', ' ').replace('_', ' ').split()
        if words:
            # 首字母缩写
            alias.append(''.join([w[0] for w in words]))
            # 简短形式
            if len(words) > 1:
                alias.append(words[0].lower())
        return alias

    def add(self, name: str, path: str, alias: List[str] = None, description: str = "") -> Tuple[bool, str]:
        """
        添加项目

        Args:
            name: 项目名称
            path: 项目路径
            alias: 别名列表
            description: 项目描述

        Returns:
            (success, message)
        """
        # 展开路径
        expanded_path = os.path.expanduser(path)

        # 验证目录存在
        if not os.path.isdir(expanded_path):
            return False, f"❌ 目录不存在：{expanded_path}"

        # 检查名称冲突
        if name in self.projects:
            return False, f"❌ 项目名称已存在：{name}"

        # 创建项目
        self.projects[name] = Project(
            name=name,
            path=expanded_path,
            alias=alias or [],
            description=description
        )

        self.save()
        return True, f"✅ 项目已添加：{name}"

    def remove(self, name: str) -> Tuple[bool, str]:
        """
        删除项目

        Args:
            name: 项目名称

        Returns:
            (success, message)
        """
        if name not in self.projects:
            return False, f"❌ 项目不存在：{name}"

        del self.projects[name]
        self.save()
        return True, f"✅ 项目已删除：{name}"

    def get(self, identifier: str) -> Optional[Project]:
        """
        根据名称或别名获取项目

        Args:
            identifier: 项目名称或别名

        Returns:
            项目对象，不存在则返回 None
        """
        # 直接匹配名称
        if identifier in self.projects:
            return self.projects[identifier]

        # 匹配别名
        for proj in self.projects.values():
            if identifier in proj.alias:
                return proj

        return None

    def list_all(self) -> List[Project]:
        """获取所有项目列表"""
        return list(self.projects.values())

    def search(self, keyword: str) -> List[Project]:
        """
        搜索项目

        Args:
            keyword: 搜索关键词（匹配名称、别名或描述）

        Returns:
            匹配的项目列表
        """
        keyword = keyword.lower()
        results = []

        for proj in self.projects.values():
            if (keyword in proj.name.lower() or
                keyword in proj.description.lower() or
                any(keyword in a.lower() for a in proj.alias)):
                results.append(proj)

        return results

    def format_list(self, projects: List[Project] = None, current_path: str = None) -> str:
        """
        格式化项目列表

        Args:
            projects: 要显示的项目列表，为 None 则显示所有
            current_path: 当前工作目录路径（用于标记）

        Returns:
            格式化的项目列表字符串
        """
        if projects is None:
            projects = self.list_all()

        if not projects:
            return "📭 没有项目"

        # 按名称排序
        projects = sorted(projects, key=lambda p: p.name)

        lines = ["📁 项目列表：\n"]

        for i, proj in enumerate(projects, 1):
            # 标记当前项目
            current_marker = " 📍 *当前*" if (current_path and proj.path == current_path) else ""

            # 格式化别名
            alias_str = f" ({', '.join(proj.alias)})" if proj.alias else ""

            lines.append(
                f"  {i}. **{proj.name}**{alias_str}{current_marker}\n"
                f"     路径: `{proj.path}`\n"
                f"     描述: {proj.description or '无描述'}\n"
            )

        return "\n".join(lines)
