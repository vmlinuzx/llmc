#!/usr/bin/env python3
"""
LLMC Template Deployer

A tool for deploying LLMC templates to target repositories with intelligent
path adjustment, configuration merging, and rollback support.
"""

import os
import sys
import shutil
import argparse
import json
import re
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass
import tempfile
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
DEFAULT_TEMPLATE_PATH = Path("template")
DEFAULT_LLMC_PATH = "llmc"
BACKUP_SUFFIX = ".backup"
BACKUP_DIR = "llmc_backups"
METADATA_FILE = ".llmc_deploy_metadata.json"


@dataclass
class DeployConfig:
    """Configuration for template deployment."""
    target_dir: Path
    template_path: Path
    llmc_path: str
    dry_run: bool = False
    backup: bool = True
    force: bool = False
    verbose: bool = False


@dataclass
class FileChange:
    """Represents a file change operation."""
    operation: str  # 'create', 'update', 'delete', 'backup', 'skip'
    path: Path
    reason: str
    old_content: Optional[str] = None
    new_content: Optional[str] = None


class TemplateDeployer:
    """Main class for deploying LLMC templates to repositories."""
    
    def __init__(self, config: DeployConfig):
        self.config = config
        self.changes: List[FileChange] = []
        self.backup_path: Optional[Path] = None
        self.metadata: Dict = {
            'timestamp': datetime.now().isoformat(),
            'target_dir': str(config.target_dir.absolute()),
            'template_path': str(config.template_path.absolute()),
            'llmc_path': config.llmc_path,
            'changes': [],
            'rollback_available': False
        }
        
    def deploy(self) -> bool:
        """
        Main deployment entry point.
        
        Returns:
            bool: True if deployment succeeded, False otherwise
        """
        try:
            logger.info("=" * 60)
            logger.info("LLMC Template Deployment Starting")
            logger.info("=" * 60)
            logger.info(f"Target directory: {self.config.target_dir}")
            logger.info(f"Template source: {self.config.template_path}")
            logger.info(f"LLMC path in target: {self.config.llmc_path}")
            logger.info(f"Dry run mode: {self.config.dry_run}")
            
            # Validate inputs
            if not self._validate_inputs():
                return False
            
            # Create backup if needed
            if self.config.backup and not self.config.dry_run:
                if not self._create_backup():
                    return False
            
            # Analyze and apply changes
            if not self._analyze_changes():
                return False
            
            # Show preview if dry run
            if self.config.dry_run:
                self._show_preview()
                return True
            
            # Apply changes
            if not self._apply_changes():
                if not self._rollback():
                    logger.error("Rollback failed! Manual intervention may be required.")
                return False
            
            # Save metadata
            self._save_metadata()
            
            logger.info("=" * 60)
            logger.info("Deployment completed successfully!")
            logger.info("=" * 60)
            
            return True
            
        except Exception as e:
            logger.error(f"Deployment failed with error: {e}", exc_info=self.config.verbose)
            if not self.config.dry_run:
                self._rollback()
            return False
    
    def _validate_inputs(self) -> bool:
        """Validate deployment inputs."""
        # Check if target directory exists
        if not self.config.target_dir.exists():
            logger.error(f"Target directory does not exist: {self.config.target_dir}")
            return False
        
        if not self.config.target_dir.is_dir():
            logger.error(f"Target path is not a directory: {self.config.target_dir}")
            return False
        
        # Check if template directory exists
        if not self.config.template_path.exists():
            logger.error(f"Template directory does not exist: {self.config.template_path}")
            return False
        
        if not self.config.template_path.is_dir():
            logger.error(f"Template path is not a directory: {self.config.template_path}")
            return False
        
        # Check if target has existing llmc directory
        target_llmc = self.config.target_dir / self.config.llmc_path
        if target_llmc.exists() and not self.config.force and not self.config.dry_run:
            logger.error(f"Target already has {self.config.llmc_path} directory. Use --force to overwrite.")
            return False
        
        return True
    
    def _create_backup(self) -> bool:
        """Create backup of existing llmc directory."""
        target_llmc = self.config.target_dir / self.config.llmc_path
        
        if not target_llmc.exists():
            logger.info("No existing llmc directory to backup.")
            return True
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{self.config.llmc_path}_{timestamp}"
        self.backup_path = self.config.target_dir / BACKUP_DIR / backup_name
        
        logger.info(f"Creating backup: {self.backup_path}")
        
        try:
            self.backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(target_llmc, self.backup_path)
            logger.info("Backup created successfully.")
            return True
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            return False
    
    def _analyze_changes(self) -> bool:
        """Analyze and plan all changes needed for deployment."""
        logger.info("Analyzing changes...")
        
        target_llmc = self.config.target_dir / self.config.llmc_path
        
        # Check if llmc directory exists
        if target_llmc.exists():
            # Check for conflicts
            conflicts = self._find_conflicts(target_llmc)
            if conflicts and not self.config.force:
                logger.warning("Found potential conflicts:")
                for conflict in conflicts:
                    logger.warning(f"  - {conflict}")
                logger.warning("Use --force to overwrite existing files.")
                return False
            
            # Backup existing files
            for conflict in conflicts:
                self.changes.append(FileChange(
                    operation='backup',
                    path=conflict,
                    reason='Backing up existing file before overwrite'
                ))
        
        # Plan template file deployment
        template_files = list(self.config.template_path.rglob('*'))
        for template_file in template_files:
            if template_file.is_file():
                relative_path = template_file.relative_to(self.config.template_path)
                target_file = target_llmc / relative_path
                
                self.changes.append(FileChange(
                    operation='create' if not target_file.exists() else 'update',
                    path=target_file,
                    reason=f"Deploying template file: {relative_path}"
                ))
        
        # Plan configuration merging
        if not self._plan_config_merging(target_llmc):
            return False
        
        # Plan path adjustments
        if not self._plan_path_adjustments():
            return False
        
        logger.info(f"Analysis complete. {len([c for c in self.changes if c.operation in ['create', 'update']])} files to deploy.")
        return True
    
    def _find_conflicts(self, target_llmc: Path) -> List[Path]:
        """Find files that would conflict during deployment."""
        conflicts = []
        target_files = set()
        
        if target_llmc.exists():
            for root, dirs, files in os.walk(target_llmc):
                for file in files:
                    target_files.add(Path(root) / file)
        
        template_files = set()
        for root, dirs, files in os.walk(self.config.template_path):
            for file in files:
                template_files.add(Path(root) / file)
        
        # Convert template paths to target paths
        template_root = self.config.template_path
        for template_file in template_files:
            relative = template_file.relative_to(template_root)
            target_file = target_llmc / relative
            if target_file in target_files:
                conflicts.append(target_file)
        
        return conflicts
    
    def _plan_config_merging(self, target_llmc: Path) -> bool:
        """Plan configuration file merging strategy."""
        logger.info("Planning configuration merging...")
        
        # Check for existing config files
        config_dir = target_llmc / "config"
        if config_dir.exists():
            local_config = config_dir / "local.toml"
            if local_config.exists():
                self.changes.append(FileChange(
                    operation='skip',
                    path=local_config,
                    reason='Preserving existing local.toml configuration'
                ))
            else:
                # Create local.example.toml if it doesn't exist
                example_config = config_dir / "local.example.toml"
                self.changes.append(FileChange(
                    operation='create',
                    path=example_config,
                    reason='Creating local configuration example'
                ))
        
        return True
    
    def _plan_path_adjustments(self) -> bool:
        """Plan path adjustments for files that need updates."""
        logger.info("Planning path adjustments...")
        
        # Find files that might need path adjustments
        patterns = [
            (r'(?i)scripts?/', f'{self.config.llmc_path}/scripts/'),
            (r'(?i)tools/', f'{self.config.llmc_path}/tools/'),
            (r'(?i)config/', f'{self.config.llmc_path}/config/'),
            (r'\.\./tools', f'../{self.config.llmc_path}/tools'),
            (r'\.\./scripts', f'../{self.config.llmc_path}/scripts'),
        ]
        
        for template_file in self.config.template_path.rglob('*'):
            if template_file.is_file() and template_file.suffix in ['.sh', '.py', '.js', '.json', '.toml', '.md']:
                relative_path = template_file.relative_to(self.config.template_path)
                target_file = self.config.target_dir / self.config.llmc_path / relative_path
                
                # Check if file needs path adjustments
                try:
                    with open(template_file, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    needs_adjustment = any(re.search(pattern[0], content, re.MULTILINE) 
                                           for pattern in patterns)
                    
                    if needs_adjustment:
                        self.changes.append(FileChange(
                            operation='update',
                            path=target_file,
                            reason='Adjusting paths for new structure',
                            old_content=None,
                            new_content=content  # Will be processed in apply
                        ))
                except Exception as e:
                    logger.debug(f"Could not read {template_file}: {e}")
        
        return True
    
    def _show_preview(self):
        """Show preview of all planned changes."""
        logger.info("\n" + "=" * 60)
        logger.info("DEPLOYMENT PREVIEW (Dry Run)")
        logger.info("=" * 60)
        
        # Group changes by operation
        operations = {}
        for change in self.changes:
            if change.operation not in operations:
                operations[change.operation] = []
            operations[change.operation].append(change)
        
        for op, changes in operations.items():
            logger.info(f"\n{op.upper()} ({len(changes)} items):")
            for change in changes:
                logger.info(f"  {change.path.relative_to(self.config.target_dir)}")
                logger.info(f"    Reason: {change.reason}")
        
        if self.backup_path:
            logger.info(f"\nBackup will be created at: {self.backup_path.relative_to(self.config.target_dir)}")
    
    def _apply_changes(self) -> bool:
        """Apply all planned changes."""
        logger.info("\nApplying changes...")
        
        for change in self.changes:
            try:
                if change.operation == 'backup':
                    self._backup_file(change)
                elif change.operation == 'create':
                    self._create_file(change)
                elif change.operation == 'update':
                    self._update_file(change)
                elif change.operation == 'skip':
                    logger.info(f"Skipped: {change.path.relative_to(self.config.target_dir)}")
            except Exception as e:
                logger.error(f"Failed to apply change for {change.path}: {e}")
                return False
        
        return True
    
    def _backup_file(self, change: FileChange):
        """Backup an existing file."""
        backup_file = change.path.with_suffix(change.path.suffix + BACKUP_SUFFIX)
        logger.info(f"Backing up: {change.path.relative_to(self.config.target_dir)}")
        shutil.copy2(change.path, backup_file)
    
    def _create_file(self, change: FileChange):
        """Create a new file from template."""
        logger.info(f"Creating: {change.path.relative_to(self.config.target_dir)}")
        
        # Create parent directories
        change.path.parent.mkdir(parents=True, exist_ok=True)
        
        # Get source file
        relative_path = change.path.relative_to(self.config.target_dir / self.config.llmc_path)
        source_file = self.config.template_path / relative_path
        
        # Copy file
        shutil.copy2(source_file, change.path)
        
        # Apply path adjustments if needed
        self._adjust_file_paths(change.path)
    
    def _update_file(self, change: FileChange):
        """Update an existing file."""
        logger.info(f"Updating: {change.path.relative_to(self.config.target_dir)}")
        
        # Get source file
        relative_path = change.path.relative_to(self.config.target_dir / self.config.llmc_path)
        source_file = self.config.template_path / relative_path
        
        # Create backup first
        backup_file = change.path.with_suffix(change.path.suffix + BACKUP_SUFFIX)
        shutil.copy2(change.path, backup_file)
        
        # Copy and adjust
        shutil.copy2(source_file, change.path)
        self._adjust_file_paths(change.path)
    
    def _adjust_file_paths(self, file_path: Path):
        """Adjust paths within a file to match the new structure."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            original_content = content
            llmc_path = self.config.llmc_path
            
            # Common path adjustments
            adjustments = [
                # Relative path adjustments
                (r'(\.\.\/)+tools', f'../{llmc_path}/tools'),
                (r'(\.\.\/)+scripts', f'../{llmc_path}/scripts'),
                (r'(\.\.\/)+config', f'../{llmc_path}/config'),
                
                # Absolute path adjustments
                (r'(?i)(?<![a-zA-Z0-9_/])tools\/', f'{llmc_path}/tools/'),
                (r'(?i)(?<![a-zA-Z0-9_/])scripts\/', f'{llmc_path}/scripts/'),
                (r'(?i)(?<![a-zA-Z0-9_/])config\/', f'{llmc_path}/config/'),
                
                # SCRIPT_ROOT adjustments
                (r'SCRIPT_ROOT="[^"]*"', f'SCRIPT_ROOT="$(cd "$(dirname "${{BASH_SOURCE[0]}}")/.." && pwd)"'),
            ]
            
            for pattern, replacement in adjustments:
                content = re.sub(pattern, replacement, content)
            
            if content != original_content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                logger.debug(f"Adjusted paths in: {file_path.relative_to(self.config.target_dir)}")
        
        except Exception as e:
            logger.debug(f"Could not adjust paths in {file_path}: {e}")
    
    def _rollback(self) -> bool:
        """Rollback the deployment."""
        if not self.backup_path or not self.backup_path.exists():
            logger.error("No backup available for rollback.")
            return False
        
        logger.info("Rolling back deployment...")
        
        try:
            target_llmc = self.config.target_dir / self.config.llmc_path
            if target_llmc.exists():
                shutil.rmtree(target_llmc)
            
            shutil.copytree(self.backup_path, target_llmc)
            logger.info("Rollback completed successfully.")
            return True
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False
    
    def _save_metadata(self):
        """Save deployment metadata."""
        metadata_file = self.config.target_dir / self.config.llmc_path / METADATA_FILE
        
        try:
            # Convert changes to serializable format
            metadata_changes = []
            for change in self.changes:
                metadata_changes.append({
                    'operation': change.operation,
                    'path': str(change.path.relative_to(self.config.target_dir)),
                    'reason': change.reason
                })
            
            self.metadata['changes'] = metadata_changes
            self.metadata['rollback_available'] = self.backup_path is not None
            if self.backup_path:
                self.metadata['backup_path'] = str(self.backup_path.relative_to(self.config.target_dir))
            
            metadata_file.parent.mkdir(parents=True, exist_ok=True)
            with open(metadata_file, 'w') as f:
                json.dump(self.metadata, f, indent=2)
            
            logger.info(f"Metadata saved to: {metadata_file.relative_to(self.config.target_dir)}")
        except Exception as e:
            logger.warning(f"Could not save metadata: {e}")


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="Deploy LLMC template to target repositories",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Deploy template to current directory
  llmc deploy .
  
  # Deploy to specific repository
  llmc deploy /path/to/repo
  
  # Dry run to preview changes
  llmc deploy /path/to/repo --dry-run
  
  # Force deployment (overwrite existing)
  llmc deploy /path/to/repo --force
  
  # Deploy without backup
  llmc deploy /path/to/repo --no-backup
  
  # Use custom template path
  llmc deploy /path/to/repo --template /path/to/template
  
  # Verbose output
  llmc deploy /path/to/repo --verbose
        """
    )
    
    parser.add_argument(
        'target_dir',
        help='Target directory to deploy template to'
    )
    
    parser.add_argument(
        '--template',
        type=Path,
        default=DEFAULT_TEMPLATE_PATH,
        help=f'Path to template directory (default: {DEFAULT_TEMPLATE_PATH})'
    )
    
    parser.add_argument(
        '--llmc-path',
        type=str,
        default=DEFAULT_LLMC_PATH,
        help=f'Path for llmc directory in target (default: {DEFAULT_LLMC_PATH})'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without applying them'
    )
    
    parser.add_argument(
        '--no-backup',
        action='store_true',
        help='Skip creating backup of existing llmc directory'
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force deployment even if llmc directory exists'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    
    parser.add_argument(
        '--rollback',
        type=str,
        metavar='BACKUP_PATH',
        help='Rollback to a specific backup (use with backup directory name)'
    )
    
    args = parser.parse_args()
    
    # Handle rollback
    if args.rollback:
        # This is a separate rollback command
        target_dir = Path(args.target_dir)
        backup_path = target_dir / BACKUP_DIR / args.rollback
        
        if not backup_path.exists():
            logger.error(f"Backup not found: {backup_path}")
            sys.exit(1)
        
        logger.info(f"Rolling back to: {backup_path}")
        llmc_path = target_dir / DEFAULT_LLMC_PATH
        
        try:
            if llmc_path.exists():
                shutil.rmtree(llmc_path)
            shutil.copytree(backup_path, llmc_path)
            logger.info("Rollback completed successfully.")
            sys.exit(0)
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            sys.exit(1)
    
    # Create configuration
    config = DeployConfig(
        target_dir=Path(args.target_dir).absolute(),
        template_path=args.template.absolute() if args.template else DEFAULT_TEMPLATE_PATH,
        llmc_path=args.llmc_path,
        dry_run=args.dry_run,
        backup=not args.no_backup,
        force=args.force,
        verbose=args.verbose
    )
    
    # Run deployment
    deployer = TemplateDeployer(config)
    success = deployer.deploy()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
