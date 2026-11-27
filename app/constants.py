"""Fixed lists used across the app: Schedule E categories, payment kinds, etc.

Schedule E (Form 1040) line numbers have been stable for years. If the IRS
renumbers a line, change it here and every report follows.
"""

# Expense categories. `line` is the Schedule E line number; None means the
# money is tracked but is NOT a Schedule E deduction (your CPA still needs it).
EXPENSE_CATEGORIES = [
    {"key": "advertising", "label": "Advertising", "line": 5,
     "hint": "Listing fees, signs, Zillow / Facebook ads."},
    {"key": "auto_travel", "label": "Auto and travel", "line": 6,
     "hint": "Driving to properties: miles × IRS rate, or actual costs. Keep a mileage note."},
    {"key": "cleaning_maintenance", "label": "Cleaning and maintenance", "line": 7,
     "hint": "Lawn care, snow removal, pest control, cleaning between tenants."},
    {"key": "commissions", "label": "Commissions", "line": 8,
     "hint": "Leasing or placement fees paid to an agent."},
    {"key": "insurance", "label": "Insurance", "line": 9,
     "hint": "Landlord / hazard, umbrella, flood. Paid directly or out of escrow."},
    {"key": "legal_professional", "label": "Legal and other professional fees", "line": 10,
     "hint": "CPA, attorney, eviction filings, LLC filing fees."},
    {"key": "management", "label": "Management fees", "line": 11,
     "hint": "Property manager percentage or flat fees."},
    {"key": "mortgage_interest", "label": "Mortgage interest", "line": 12,
     "hint": "Interest part of the payment only. Match it to your Form 1098 at year end."},
    {"key": "other_interest", "label": "Other interest", "line": 13,
     "hint": "Interest on a HELOC, credit card or loan used for the rental."},
    {"key": "repairs", "label": "Repairs", "line": 14,
     "hint": "Fixing what broke: plumber, furnace repair, patching drywall."},
    {"key": "supplies", "label": "Supplies", "line": 15,
     "hint": "Light bulbs, filters, locks, small tools, cleaning supplies."},
    {"key": "taxes", "label": "Taxes", "line": 16,
     "hint": "Property taxes (directly or from escrow). Not income tax."},
    {"key": "utilities", "label": "Utilities", "line": 17,
     "hint": "Water, sewer, trash, gas, electric that you pay as the owner."},
    {"key": "other", "label": "Other", "line": 19,
     "hint": "HOA dues, bank fees, software, permits, anything that fits nowhere else."},
    # Tracked, not deducted on Schedule E
    {"key": "capital_improvement", "label": "Capital improvement", "line": None,
     "hint": "New roof, HVAC, full remodel. Depreciated over years, not expensed. Your CPA needs these."},
    {"key": "mortgage_principal", "label": "Mortgage principal", "line": None,
     "hint": "Principal part of the payment. Not deductible, but useful for cash flow."},
    {"key": "escrow", "label": "Escrow deposit", "line": None,
     "hint": "The escrow part of a mortgage payment. When the lender pays taxes or insurance from escrow, log those under Taxes / Insurance."},
    {"key": "deposit_refund", "label": "Security deposit refund", "line": None,
     "hint": "Returning a tenant's deposit. Not an expense."},
]

CATEGORY_BY_KEY = {c["key"]: c for c in EXPENSE_CATEGORIES}
DEDUCTIBLE_KEYS = [c["key"] for c in EXPENSE_CATEGORIES if c["line"] is not None]
NON_DEDUCTIBLE_KEYS = [c["key"] for c in EXPENSE_CATEGORIES if c["line"] is None]

# Loose words people type in a spreadsheet -> category key (used by CSV import).
CATEGORY_ALIASES = {
    "ads": "advertising", "advertisement": "advertising", "listing": "advertising", "zillow": "advertising",
    "auto": "auto_travel", "travel": "auto_travel", "mileage": "auto_travel", "miles": "auto_travel",
    "cleaning": "cleaning_maintenance", "maintenance": "cleaning_maintenance", "lawn": "cleaning_maintenance",
    "lawn care": "cleaning_maintenance", "landscaping": "cleaning_maintenance", "snow": "cleaning_maintenance",
    "snow removal": "cleaning_maintenance", "pest control": "cleaning_maintenance",
    "commission": "commissions", "leasing fee": "commissions",
    "legal": "legal_professional", "attorney": "legal_professional", "lawyer": "legal_professional",
    "accountant": "legal_professional", "cpa": "legal_professional", "eviction": "legal_professional",
    "professional fees": "legal_professional",
    "management fee": "management", "property management": "management", "pm fee": "management",
    "interest": "mortgage_interest", "mortgage": "mortgage_interest",
    "repair": "repairs", "plumbing": "repairs", "plumber": "repairs", "hvac repair": "repairs",
    "supply": "supplies",
    "tax": "taxes", "property tax": "taxes", "property taxes": "taxes", "real estate tax": "taxes",
    "utility": "utilities", "water": "utilities", "sewer": "utilities", "trash": "utilities",
    "electric": "utilities", "electricity": "utilities", "gas bill": "utilities",
    "hoa": "other", "bank fee": "other", "software": "other", "permit": "other", "misc": "other",
    "capex": "capital_improvement", "improvement": "capital_improvement", "capital": "capital_improvement",
    "principal": "mortgage_principal",
    "deposit refund": "deposit_refund", "deposit returned": "deposit_refund",
}

# Money coming in.
PAYMENT_KINDS = [
    {"key": "rent", "label": "Rent", "income": True, "rent": True},
    {"key": "hap", "label": "Section 8 (HAP)", "income": True, "rent": True},
    {"key": "late_fee", "label": "Late fee", "income": True, "rent": False},
    {"key": "other", "label": "Other income", "income": True, "rent": False},
    {"key": "deposit", "label": "Security deposit", "income": False, "rent": False},
    {"key": "deposit_kept", "label": "Deposit kept", "income": True, "rent": False},
]
KIND_BY_KEY = {k["key"]: k for k in PAYMENT_KINDS}
INCOME_KINDS = [k["key"] for k in PAYMENT_KINDS if k["income"]]
RENT_KINDS = [k["key"] for k in PAYMENT_KINDS if k["rent"]]

KIND_ALIASES = {
    "section 8": "hap", "section8": "hap", "s8": "hap", "housing": "hap", "housing authority": "hap",
    "late": "late_fee", "late fee": "late_fee", "fee": "late_fee",
    "deposit": "deposit", "security deposit": "deposit", "sd": "deposit",
    "kept deposit": "deposit_kept", "deposit applied": "deposit_kept",
    "pet fee": "other", "other income": "other", "laundry": "other",
}

PAYMENT_METHODS = ["Cash", "Check", "Money order", "Zelle", "Cash App", "Venmo", "ACH / bank transfer",
                   "Card", "Housing authority", "Other"]

CONTACT_ROLES = ["Contractor", "Plumber", "Electrician", "HVAC", "Roofer", "Handyman", "Lawn / snow",
                 "Cleaner", "Pest control", "Insurance", "Lender", "Housing authority", "Attorney",
                 "Accountant", "Property manager", "Utility", "City / county", "Other"]

PROPERTY_TYPES = [("single_family", "Single family"), ("duplex", "Duplex"), ("triplex", "Triplex"),
                  ("fourplex", "Fourplex"), ("multi", "Multifamily (5+)"), ("condo", "Condo / townhome"),
                  ("commercial", "Commercial")]

MAINTENANCE_STATUSES = [("open", "Open"), ("scheduled", "Scheduled"), ("done", "Done")]

ALLOWED_UPLOADS = {"pdf", "jpg", "jpeg", "png", "heic", "heif", "webp", "gif", "doc", "docx",
                   "xls", "xlsx", "csv", "txt"}
