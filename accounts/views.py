import jwt
from datetime import datetime, timedelta, timezone
from django.conf import settings
from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Q
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from .serializers import MultiBankLoginRequestSerializer

from .models import BankUser, Account, Bank, Transfer, Withdrawal
from .serializers import (
    UniversalRegistrationSerializer, 
    BankEnrollmentSerializer,
    BankUserSerializer,
    TransferSerializer,
    WithdrawalSerializer,
    AccountBalanceSerializer
)

# ========================================================================
# ─── UTILITY SECURITY GUARD ───
# ========================================================================
def verify_web_session(request):
    """
    Feature 7: Decodes the session token from the authorization header.
    Returns the payload dictionary if valid, or an error string if expired/tampered.
    """
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return "Session manquante ou invalide. Authentification requise."

    token = auth_header.split(' ')[1]
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        return payload  # Valid active session window verified
    except jwt.ExpiredSignatureError:
        return "Votre session a expiré après 30 minutes d'inactivité. Veuillez vous reconnecter."
    except jwt.InvalidTokenError:
        return "Token de session altéré, corrompu ou invalide."


# ========================================================================
# ─── 1. OPTIMIZED SHARDING LOGIN VIEW (Module 3 & Feature 5, 6, 7) ───
# ========================================================================
class MultiBankLoginView(APIView):
    """
    Optimized login view tracking 3-strike lockouts and issuing a 
    strict 30-minute session payload token for web client validation.
    """

    @extend_schema(
        request=MultiBankLoginRequestSerializer,
        responses={200: serializers.Serializer},  # Keeps output generic
        summary="Authentification Multi-Banque",
        description="Permet à un utilisateur de se connecter au contexte spécifique d'une banque en utilisant son matricule/email et un mot de passe préfixé (ex: UBC_password)."
    )
    def post(self, request):
        identifier = request.data.get('identifier')
        password = request.data.get('password')

        # 1. Check for missing fields
        if not identifier or not password:
            return Response(
                {"error": "Identifiants de connexion manquants."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # 2. Find the global user
        user = BankUser.objects.filter(Q(email=identifier) | Q(matricule=identifier)).first()
        if not user:
            return Response(
                {"error": "Identifiants incorrects ou utilisateur introuvable."}, 
                status=status.HTTP_401_UNAUTHORIZED
            )

        # 3. Handle blocked accounts
        if user.status == 'BLOCKED':
            return Response(
                {"error": "Compte verrouillé suite à 3 échecs consécutifs. Veuillez contacter un administrateur."}, 
                status=status.HTTP_403_FORBIDDEN
            )

        # 4. Parse password prefix constraint
        if "_" not in password:
            return Response(
                {"error": "Format du mot de passe invalide. Le mot de passe doit inclure le préfixe de la banque (Ex: UBC_...)."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        password_prefix, raw_user_password = password.split("_", 1)

        # 5. Verify targeted bank exists
        bank_exists = Bank.objects.filter(code=password_prefix).exists()
        if not bank_exists:
            return Response(
                {"error": "Le code banque spécifié dans le mot de passe n'existe pas."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # 6. Evaluate credentials
        if user.check_password(password):
            # Reset failures on successful verification
            user.failed_login_attempts = 0
            user.save()

            # Verify the user actually holds a checking account at that specific branch node
            active_workspace_account = Account.objects.filter(owner=user, bank__code=password_prefix).first()
            if not active_workspace_account:
                return Response(
                    {"error": f"Vous n'avez pas de compte actif configuré au sein de la banque {password_prefix}."}, 
                    status=status.HTTP_404_NOT_FOUND
                )

            # 7. Issue secure transactional JWT Token valid for 30 minutes
            expiration_time = datetime.now(timezone.utc) + timedelta(minutes=30)
            
            session_payload = {
                "matricule": user.matricule,
                "active_bank": password_prefix,
                "account_id": str(active_workspace_account.account_id),
                "exp": int(expiration_time.timestamp())
            }
            
            session_token = jwt.encode(session_payload, settings.SECRET_KEY, algorithm='HS256')

            return Response({
                "message": "Connexion réussie.",
                "session_token": session_token,
                "expires_in": "1800 seconds (30 mins)",
                "user_full_name": user.full_name,
                "current_bank_context": password_prefix,
                "account_details": {
                    "account_id": str(active_workspace_account.account_id),
                    "bank_name": active_workspace_account.bank.name,
                    "balance": float(active_workspace_account.balance),
                    "matricule": user.matricule
                }
            }, status=status.HTTP_200_OK)
            
        else:
            # Increment failed attempts on wrong credentials
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= 3:
                user.status = 'BLOCKED'
                user.save()
                return Response(
                    {"error": "Sécurité : Compte bloqué suite à 3 tentatives infructueuses."}, 
                    status=status.HTTP_403_FORBIDDEN
                )
            user.save()
                
            return Response(
                {"error": "Identifiants incorrects. Mot de passe ou Matricule invalide."}, 
                status=status.HTTP_401_UNAUTHORIZED
            )


# =====================================================================
# ─── 2. UNIVERSAL USER CRUD ENDPOINTS (Module 1 - CRUD Users) ───
# =====================================================================
class UniversalRegistrationView(generics.CreateAPIView):
    """Feature 2: Registers user profile, grants account ledger row, and credits local wallet with 100,000 FCFA."""
    serializer_class = UniversalRegistrationSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"message": "Utilisateur et premier compte créés avec succès, 100 000 FCFA injectés dans le portefeuille local."}, 
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BankUserListView(generics.ListAPIView):
    """Lists all registered universal profiles across the clearing network."""
    queryset = BankUser.objects.all()
    serializer_class = BankUserSerializer


class BankUserDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Manages individual user information records using their matricule sequence string."""
    queryset = BankUser.objects.all()
    serializer_class = BankUserSerializer
    lookup_field = 'matricule'


# =====================================================================
# ─── 3. MULTI-BANK ENROLLMENT ENDPOINT (Feature 10) ───
# =====================================================================
class BankEnrollmentView(APIView):
    """Enables an existing matricule entity to spin up an account ledger node at a secondary commercial bank."""
    @extend_schema(request=BankEnrollmentSerializer)
    def post(self, request):
        serializer = BankEnrollmentSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"message": "Inscription à la nouvelle banque effectuée avec succès."}, 
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# =====================================================================
# ─── 4. ADMINISTRATIVE UNBLOCK OVERRIDE ENDPOINT (Feature 6) ───
# =====================================================================
class AdminUnblockUserView(APIView):
    """Administrative override tool to restore BLOCKED customer profiles back to ACTIVE state."""
    def post(self, request, matricule):
        try:
            target_user = BankUser.objects.get(matricule=matricule)
        except BankUser.DoesNotExist:
            return Response(
                {"error": "Aucun utilisateur trouvé avec ce matricule dans le système."}, 
                status=status.HTTP_404_NOT_FOUND
            )

        target_user.status = 'ACTIVE'
        target_user.failed_login_attempts = 0
        target_user.save()

        return Response(
            {"message": f"Le profil de l'utilisateur {target_user.full_name} a été débloqué avec succès."}, 
            status=status.HTTP_200_OK
        )


# =====================================================================
# ─── 5. FINANCIAL TRANSACTIONS ENGINE (Modules 4 & 5) ───
# =====================================================================
class TransferCreateView(APIView):
    """Executes a financial transfer processing atomic balances and charging system routing fees."""
    def post(self, request):
        session = verify_web_session(request)
        if isinstance(session, str):
            return Response({"error": session}, status=status.HTTP_401_UNAUTHORIZED)

        serializer = TransferSerializer(data=request.data)
        if serializer.is_valid():
            try:
                transfer = serializer.save()
                return Response({
                    "message": "Virement effectué avec succès.",
                    "transaction_id": str(transfer.transaction_id),
                    "amount": float(transfer.amount),
                    "fee": float(transfer.fee)
                }, status=status.HTTP_201_CREATED)
            except ValueError as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class WithdrawalCreateView(APIView):
    """Processes a structural checking account cash-out extraction charging a flat 50.00 FCFA fee."""
    def post(self, request):
        session = verify_web_session(request)
        if isinstance(session, str):
            return Response({"error": session}, status=status.HTTP_401_UNAUTHORIZED)

        serializer = WithdrawalSerializer(data=request.data)
        if serializer.is_valid():
            try:
                withdrawal = serializer.save()
                return Response({
                    "message": "Retrait enregistré avec succès.",
                    "transaction_id": str(withdrawal.transaction_id),
                    "amount": float(withdrawal.amount),
                    "fee": float(withdrawal.fee)
                }, status=status.HTTP_201_CREATED)
            except ValueError as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# =====================================================================
# ─── 6. INFORMATION SEARCH & HISTORY VIEWS ───
# =====================================================================
class AccountDetailView(APIView):
    """Returns granular tracking balances and profile parameters for a specific ledger account ID."""
    def get(self, request, account_id):
        session = verify_web_session(request)
        if isinstance(session, str):
            return Response({"error": session}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            account = Account.objects.get(account_id=account_id)
        except Account.DoesNotExist:
            return Response({"error": "Compte bancaire introuvable."}, status=status.HTTP_404_NOT_FOUND)

        serializer = AccountBalanceSerializer(account)
        return Response(serializer.data, status=status.HTTP_200_OK)


class UserAccountsListView(APIView):
    """Retrieves all decentralized bank account nodes connected to a client's Matricule code."""
    def get(self, request, matricule):
        session = verify_web_session(request)
        if isinstance(session, str):
            return Response({"error": session}, status=status.HTTP_401_UNAUTHORIZED)

        accounts = Account.objects.filter(owner__matricule=matricule)
        serializer = AccountBalanceSerializer(accounts, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class UnifiedTransactionHistoryView(APIView):
    """Gathers transfers and withdrawals for an account into a single chronological feed."""
    def get(self, request, account_id):
        session = verify_web_session(request)
        if isinstance(session, str):
            return Response({"error": session}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            account = Account.objects.get(account_id=account_id)
        except Account.DoesNotExist:
            return Response({"error": "Compte bancaire introuvable."}, status=status.HTTP_404_NOT_FOUND)

        transfers = Transfer.objects.filter(Q(sender=account) | Q(receiver=account)).order_by('-timestamp')
        withdrawals = Withdrawal.objects.filter(account=account).order_by('-timestamp')

        feed = []

        for t in transfers:
            is_sender = (t.sender == account)
            feed.append({
                "type": "TRANSFER_SENT" if is_sender else "TRANSFER_RECEIVED",
                "transaction_id": str(t.transaction_id),
                "amount": float(t.amount),
                "fee": float(t.fee) if is_sender else 0.00,
                "date": t.timestamp.isoformat(),
                "partner_account": str(t.receiver.account_id) if is_sender else str(t.sender.account_id),
                "partner_name": t.receiver.owner.full_name if is_sender else t.sender.owner.full_name,
                "bank_context": t.receiver.bank.code if is_sender else t.sender.bank.code
            })

        for w in withdrawals:
            feed.append({
                "type": "WITHDRAWAL",
                "transaction_id": str(w.transaction_id),
                "amount": float(w.amount),
                "fee": float(w.fee),
                "date": w.timestamp.isoformat(),
                "partner_account": "Guichet Automatique",
                "partner_name": "Cash Out Extraction",
                "bank_context": account.bank.code
            })

        feed.sort(key=lambda x: x['date'], reverse=True)

        return Response({
            "account_id": str(account.account_id),
            "current_balance": float(account.balance),
            "transactions_count": len(feed),
            "history": feed
        }, status=status.HTTP_200_OK)