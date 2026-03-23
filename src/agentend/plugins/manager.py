"""Plugin manager for agentend framework."""

from typing import Optional, Dict, Any, List
from pathlib import Path
import json
import logging
import importlib.util

from agentend.plugins.hooks import HookRegistry


logger = logging.getLogger(__name__)


class PluginManifest:
    """Plugin manifest configuration."""

    def __init__(self, manifest_dict: dict):
        """
        Initialize manifest.

        Args:
            manifest_dict: Manifest dictionary from plugin.json.
        """
        self.name: str = manifest_dict.get("name", "unknown")
        self.version: str = manifest_dict.get("version", "0.0.0")
        self.description: str = manifest_dict.get("description", "")
        self.entry_point: str = manifest_dict.get("entry_point", "")
        self.hooks: List[str] = manifest_dict.get("hooks", [])
        self.requirements: List[str] = manifest_dict.get("requirements", [])
        self.config: Dict[str, Any] = manifest_dict.get("config", {})


class Plugin:
    """Loaded plugin instance."""

    def __init__(
        self,
        manifest: PluginManifest,
        module: Any,
        instance: Optional[Any] = None,
    ):
        """
        Initialize plugin.

        Args:
            manifest: Plugin manifest.
            module: Loaded Python module.
            instance: Instantiated plugin (if applicable).
        """
        self.manifest = manifest
        self.module = module
        self.instance = instance
        self.hooks: Dict[str, List[callable]] = {}


class PluginManager:
    """
    Plugin system manager.

    Loads plugins from manifests, registers hooks, and manages plugin lifecycle.
    """

    def __init__(self):
        """Initialize plugin manager."""
        self.plugins: Dict[str, Plugin] = {}
        self.hooks = HookRegistry()
        self.plugin_paths: List[Path] = []

    def add_plugin_path(self, path: str) -> None:
        """
        Add path to search for plugins.

        Args:
            path: Path to plugin directory.
        """
        self.plugin_paths.append(Path(path))
        logger.info(f"Added plugin path: {path}")

    async def load_plugin(self, manifest_path: str) -> Plugin:
        """
        Load a plugin from manifest file.

        Args:
            manifest_path: Path to plugin.json manifest.

        Returns:
            Loaded Plugin instance.

        Raises:
            ValueError: If manifest or plugin invalid.
        """
        manifest_file = Path(manifest_path)
        if not manifest_file.exists():
            raise ValueError(f"Manifest not found: {manifest_path}")

        # Load manifest
        with open(manifest_file, "r") as f:
            manifest_dict = json.load(f)

        manifest = PluginManifest(manifest_dict)
        plugin_dir = manifest_file.parent

        # Load module
        try:
            entry_point = manifest.entry_point
            module_path = plugin_dir / entry_point

            if not module_path.exists():
                raise ValueError(f"Entry point not found: {entry_point}")

            spec = importlib.util.spec_from_file_location(
                manifest.name,
                module_path,
            )
            if spec is None or spec.loader is None:
                raise ValueError(f"Cannot load module: {entry_point}")

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

        except Exception as e:
            raise ValueError(f"Failed to load plugin {manifest.name}: {e}")

        # Create plugin instance
        plugin = Plugin(manifest, module)

        # Check for hook handlers
        for hook_name in manifest.hooks:
            handler_name = f"on_{hook_name}"
            if hasattr(module, handler_name):
                handler = getattr(module, handler_name)
                if callable(handler):
                    plugin.hooks[hook_name] = [handler]

        self.plugins[manifest.name] = plugin
        logger.info(f"Loaded plugin: {manifest.name} v{manifest.version}")

        return plugin

    async def discover_plugins(self, directory: Optional[str] = None) -> List[str]:
        """
        Discover plugins in directory.

        Args:
            directory: Directory to search (uses registered paths if None).

        Returns:
            List of discovered plugin names.
        """
        paths = [Path(directory)] if directory else self.plugin_paths

        if not paths:
            logger.warning("No plugin paths configured")
            return []

        discovered = []

        for path in paths:
            if not path.exists():
                continue

            # Look for plugin.json files
            for manifest_file in path.glob("*/plugin.json"):
                try:
                    plugin_path = manifest_file.parent.name
                    await self.load_plugin(str(manifest_file))
                    discovered.append(plugin_path)
                except Exception as e:
                    logger.error(f"Failed to load plugin {plugin_path}: {e}")

        logger.info(f"Discovered {len(discovered)} plugins")
        return discovered

    def register_hooks(self, plugin_name: str) -> None:
        """
        Register all hooks for a plugin.

        Args:
            plugin_name: Name of plugin.
        """
        if plugin_name not in self.plugins:
            raise ValueError(f"Plugin not loaded: {plugin_name}")

        plugin = self.plugins[plugin_name]

        for hook_name, handlers in plugin.hooks.items():
            for handler in handlers:
                self.hooks.register(hook_name, handler)
                logger.debug(f"Registered {plugin_name}:{hook_name}")

    def get_plugin(self, name: str) -> Optional[Plugin]:
        """
        Get loaded plugin by name.

        Args:
            name: Plugin name.

        Returns:
            Plugin or None.
        """
        return self.plugins.get(name)

    def list_plugins(self) -> List[Dict[str, Any]]:
        """
        List all loaded plugins.

        Returns:
            List of plugin info dictionaries.
        """
        return [
            {
                "name": p.manifest.name,
                "version": p.manifest.version,
                "description": p.manifest.description,
                "hooks": list(p.hooks.keys()),
            }
            for p in self.plugins.values()
        ]

    async def emit_hook(
        self,
        hook_name: str,
        context: Dict[str, Any],
    ) -> Any:
        """
        Emit a hook with context.

        Args:
            hook_name: Name of hook to emit.
            context: Context dictionary for hook.

        Returns:
            Modified context or hook result.
        """
        return await self.hooks.emit(hook_name, context)

    async def unload_plugin(self, plugin_name: str) -> None:
        """
        Unload a plugin.

        Args:
            plugin_name: Name of plugin to unload.
        """
        if plugin_name not in self.plugins:
            return

        plugin = self.plugins[plugin_name]

        # Unregister hooks
        for hook_name in plugin.hooks.keys():
            self.hooks.unregister(hook_name, plugin_name)

        del self.plugins[plugin_name]
        logger.info(f"Unloaded plugin: {plugin_name}")
