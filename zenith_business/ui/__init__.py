"""UI layer (PyQt6).

Per Master Spec §3, UI code only displays information, collects input, performs
presentation-level validation, calls services, and shows results. It never
manipulates accounting/inventory balances directly.

Stage 01 provides the application shell (top navigation, branded home screen,
status bar) and a centralized design system. No business modules live here.
"""
