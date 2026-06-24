import pytest
from unittest.mock import patch
from rest_framework.exceptions import ValidationError
from accounts.serializers import TransferSerializer
from accounts.models import BankUser, Bank, Account, Transfer

# Allow safe, isolated test database transactions
pytestmark = pytest.mark.django_db

def print_banner(title):
    """Helper function to print clean, scannable terminal dividers"""
    print(f"\n" + "="*70)
    print(f" >>> {title} ")
    print("="*70)

@pytest.fixture
def setup_banking_ecosystem():
    print_banner("FIXTURE SETUP: Provisioning Isolated Sandbox Environment")
    
    # 1. Instantiate core clearing banks
    print("[1/3] Registering Central Clearing Bank Entities...")
    ubc = Bank.objects.create(code="UBC", name="United Bank of Cameroon")
    afb = Bank.objects.create(code="AFB", name="Afriland First Bank")
    eco = Bank.objects.create(code="ECO", name="Ecobank")
    print(f"      -> Created Banks: {ubc.code}, {afb.code}, {eco.code}")
    
    # 2. Instantiate universal system user profiles
    print("[2/3] Generating Universal Identity Profiles (BankUser)...")
    sender_user = BankUser.objects.create(
        matricule="RT20260001", full_name="Sender Student", 
        email="sender@univ.cm", phone="670000001"
    )
    receiver_user = BankUser.objects.create(
        matricule="RT20260002", full_name="Receiver Student", 
        email="receiver@univ.cm", phone="670000002"
    )
    print(f"      -> Created Users: {sender_user.matricule}, {receiver_user.matricule}")
    
    # 3. Provision distinct checking accounts populated with lab parameters
    print("[3/3] Opening Bank Accounts with Initial Balances...")
    sender_account = Account.objects.create(owner=sender_user, bank=ubc, balance=500.00)
    receiver_ubc = Account.objects.create(owner=receiver_user, bank=ubc, balance=100.00)
    receiver_afb = Account.objects.create(owner=receiver_user, bank=afb, balance=100.00)
    print(f"      -> Sender Account ({ubc.code}): {sender_account.balance} XAF")
    print(f"      -> Receiver Account ({ubc.code}): {receiver_ubc.balance} XAF")
    print(f"      -> Receiver Account ({afb.code}): {receiver_afb.balance} XAF")
    
    return {
        "sender_acc": sender_account,
        "receiver_ubc": receiver_ubc,
        "receiver_afb": receiver_afb,
        "receiver_user": receiver_user,
        "banks": {"UBC": ubc, "AFB": afb, "ECO": eco}
    }


# =====================================================================
# TC1: Verify system behavior when a non-existent receiver matricule is provided
# =====================================================================
def test_tc1_transfer_receiver_not_found(setup_banking_ecosystem):
    print_banner("EXECUTION: TC1 - Testing Invalid Receiver Routing Safeguard")
    
    data = {
        "sender_account_id": str(setup_banking_ecosystem["sender_acc"].account_id),
        "receiver_matricule": "INV-9999",  # Non-existent target identity
        "receiver_bank_code": "UBC",
        "amount": 200.00
    }
    print(f"Input Payload: Sending {data['amount']} XAF to completely invalid matricule '{data['receiver_matricule']}'")
    
    serializer = TransferSerializer(data=data)
    assert serializer.is_valid()
    print(" -> Serializer data validation: PASSED (Data formats are syntactically sound)")
    
    print(" -> Executing database lookup routine inside serializer.save()...")
    with pytest.raises(ValidationError) as exc_info:
        serializer.save()
        
    print(f" -> CATCH SUCCESSFUL! Engine raised expected ValidationError: {exc_info.value}")
    assert "Target account not found in the ecosystem." in str(exc_info.value)


# =====================================================================
# TC2: Verify system behavior when sender has insufficient funds
# =====================================================================
def test_tc2_transfer_insufficient_funds(setup_banking_ecosystem):
    print_banner("EXECUTION: TC2 - Testing Ledger Overdraft Prevention Guard")
    
    data = {
        "sender_account_id": str(setup_banking_ecosystem["sender_acc"].account_id),
        "receiver_matricule": setup_banking_ecosystem["receiver_user"].matricule,
        "receiver_bank_code": "AFB",
        "amount": 800.00  # Overdrawn!
    }
    print(f"Input Payload: Attempting to send {data['amount']} XAF. (Sender only has 500.00 XAF)")
    
    serializer = TransferSerializer(data=data)
    assert serializer.is_valid()
    
    print(" -> Executing balance limits check routine inside model constraints...")
    with pytest.raises(ValidationError) as exc_info:
        serializer.save()
        
    print(f" -> CATCH SUCCESSFUL! Transaction blocked cleanly: {exc_info.value}")
    assert "Insufficient funds" in str(exc_info.value)


# =====================================================================
# TC3: Verify successful intra-bank transfer (Same bank, low fee)
# =====================================================================
def test_tc3_intra_bank_transfer_success(setup_banking_ecosystem):
    print_banner("EXECUTION: TC3 - Testing Successful Intra-Bank Clearing Path")
    
    data = {
        "sender_account_id": str(setup_banking_ecosystem["sender_acc"].account_id),
        "receiver_matricule": setup_banking_ecosystem["receiver_user"].matricule,
        "receiver_bank_code": "UBC",  # Intra-bank
        "amount": 100.00
    }
    print(f"Input Payload: Transferring {data['amount']} XAF inside the same network node ({data['receiver_bank_code']})")
    
    serializer = TransferSerializer(data=data)
    assert serializer.is_valid()
    
    print(" -> Committing records and processing intra-bank transaction logic...")
    transfer = serializer.save()
    print(f" -> Database Write Success! Generated Ledger Transaction UUID: {transfer.id}")
    
    print(" -> Synchronizing local memory blocks with persistent database state...")
    setup_banking_ecosystem["sender_acc"].refresh_from_db()
    setup_banking_ecosystem["receiver_ubc"].refresh_from_db()
    
    print(f" -> Evaluating final balances: ")
    print(f"      Sender New Balance  : {setup_banking_ecosystem['sender_acc'].balance} XAF (Expected: 390.00)")
    print(f"      Receiver New Balance: {setup_banking_ecosystem['receiver_ubc'].balance} XAF (Expected: 200.00)")
    
    assert setup_banking_ecosystem["sender_acc"].balance == 390.00
    assert setup_banking_ecosystem["receiver_ubc"].balance == 200.00


# =====================================================================
# TC4: Verify successful inter-bank transfer (Different bank, high fee)
# =====================================================================
def test_tc4_inter_bank_transfer_success(setup_banking_ecosystem):
    print_banner("EXECUTION: TC4 - Testing Successful Inter-Bank Cross-Clearing Path")
    
    data = {
        "sender_account_id": str(setup_banking_ecosystem["sender_acc"].account_id),
        "receiver_matricule": setup_banking_ecosystem["receiver_user"].matricule,
        "receiver_bank_code": "AFB",  # Cross-clearing bank
        "amount": 100.00
    }
    print(f"Input Payload: Routing {data['amount']} XAF across different network nodes (UBC -> {data['receiver_bank_code']})")
    
    serializer = TransferSerializer(data=data)
    assert serializer.is_valid()
    
    print(" -> Committing records and calculating cross-network premium routing fees...")
    transfer = serializer.save()
    print(f" -> Database Write Success! Generated Ledger Transaction UUID: {transfer.id}")
    
    print(" -> Synchronizing local memory blocks with persistent database state...")
    setup_banking_ecosystem["sender_acc"].refresh_from_db()
    setup_banking_ecosystem["receiver_afb"].refresh_from_db()
    
    print(f" -> Evaluating final balances: ")
    print(f"      Sender New Balance  : {setup_banking_ecosystem['sender_acc'].balance} XAF (Expected: 350.00)")
    print(f"      Receiver New Balance: {setup_banking_ecosystem['receiver_afb'].balance} XAF (Expected: 200.00)")
    
    assert setup_banking_ecosystem["sender_acc"].balance == 350.00
    assert setup_banking_ecosystem["receiver_afb"].balance == 200.00


# =====================================================================
# TC5: Verify that transaction.atomic rolls back changes if system crashes
# =====================================================================
def test_tc5_atomic_rollback_on_system_crash(setup_banking_ecosystem):
    print_banner("EXECUTION: TC5 - Testing ACID Atomic Transaction Integrity")
    
    data = {
        "sender_account_id": str(setup_banking_ecosystem["sender_acc"].account_id),
        "receiver_matricule": setup_banking_ecosystem["receiver_user"].matricule,
        "receiver_bank_code": "UBC",
        "amount": 100.00
    }
    print("Input Payload: Processing safe atomic balance transfer block...")
    
    serializer = TransferSerializer(data=data)
    assert serializer.is_valid()

    print(" -> Injecting artificial mid-execution infrastructure crash simulation...")
    with patch.object(Transfer, 'save', side_effect=RuntimeError("Sudden Server Power Disruption")):
        with pytest.raises(RuntimeError, match="Sudden Server Power Disruption"):
            serializer.save()
    print(" -> CRASH INTERCEPTED! Engine halted execution mid-stream.")
            
    print(" -> Checking database rows to confirm transaction rollback integrity...")
    setup_banking_ecosystem["sender_acc"].refresh_from_db()
    setup_banking_ecosystem["receiver_ubc"].refresh_from_db()
    
    print(f"      Sender Safe Rollback Balance: {setup_banking_ecosystem['sender_acc'].balance} XAF (Must equal 500.00)")
    print(f"      Receiver Safe Rollback Balance: {setup_banking_ecosystem['receiver_ubc'].balance} XAF (Must equal 100.00)")
    
    assert setup_banking_ecosystem["sender_acc"].balance == 500.00
    assert setup_banking_ecosystem["receiver_ubc"].balance == 100.00