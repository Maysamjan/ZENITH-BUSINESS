"""Business/application service layer (Stage 02 §4, §48).

Services own transactions and authorization. The UI calls services; services
compose repositories inside :meth:`Database.transaction` blocks. No UI code
executes SQL, and permission checks live here (service layer), not only in the UI.
"""
