"""Agent execution package — manages background agent execution lifecycle.

Submodules are imported directly by consumers rather than re-exported here,
to avoid circular imports through the factories → roles → task_tools chain.
"""
