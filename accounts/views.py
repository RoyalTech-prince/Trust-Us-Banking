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
@extend_schema(
    summary="Enregistrement d'utilisateur universel",
    description="Crée un profil utilisateur universel, ouvre une ligne de compte et crédite immédiatement le portefeuille local de 100 000 FCFA."
)
class UniversalRegistrationView(generics.CreateAPIView):
    """Enregistre un profil utilisateur universel, accorde une ligne de grand livre de compte et crédite le portefeuille local de 100 000 FCFA."""
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


@extend_schema(
    summary="Liste des utilisateurs universels",
    description="Retourne la liste de tous les profils utilisateurs enregistrés dans le réseau bancaire commun."
)
class BankUserListView(generics.ListAPIView):
    """Retourne la liste de tous les profils utilisateurs enregistrés dans le réseau bancaire."""
    queryset = BankUser.objects.all()
    serializer_class = BankUserSerializer


@extend_schema(
    summary="Détails d'un utilisateur",
    description="Récupère, met à jour ou supprime les informations d'un utilisateur identifié par son matricule universel."
)
class BankUserDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Gère les informations d'un utilisateur individuel par son matricule."""
    queryset = BankUser.objects.all()
    serializer_class = BankUserSerializer
    lookup_field = 'matricule'


# =====================================================================
# ─── 3. MULTI-BANK ENROLLMENT ENDPOINT (Feature 10) ───
# =====================================================================
@extend_schema(
    summary="Inscription multi-banque",
    description="Permet à un titulaire de matricule existant d'ouvrir un compte dans une nouvelle banque commerciale et de créer le nœud de grand livre correspondant."
)
class BankEnrollmentView(APIView):
    """Permet à un titulaire de matricule existant d'ouvrir un compte dans une nouvelle banque commerciale."""
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
@extend_schema(
    summary="Déblocage administratif d'un utilisateur",
    description="Permet à un administrateur de réactiver un profil utilisateur bloqué et de réinitialiser ses tentatives de connexion échouées."
)
class AdminUnblockUserView(APIView):
    """Outil d'administration pour restaurer des profils BLOQUÉS à l'état ACTIF."""
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
@extend_schema(
    summary="Effectuer un virement",
    description="Exécute un virement financier entre comptes avec traitement atomique des soldes et application des frais de routage."
)
class TransferCreateView(APIView):
    """Exécute un virement financier avec mise à jour atomique des soldes et frais de transaction."""
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


@extend_schema(
    summary="Effectuer un retrait",
    description="Traite un retrait d'argent depuis un compte courant et applique un frais fixe de 50 FCFA."
)
class WithdrawalCreateView(APIView):
    """Traite un retrait de compte courant et facture un frais fixe de 50 FCFA."""
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
@extend_schema(
    summary="Détails du compte",
    description="Renvoie les informations détaillées de solde et de profil pour un compte bancaire identifié par son UUID."
)
class AccountDetailView(APIView):
    """Renvoie les informations détaillées de solde et de profil pour un compte bancaire."""
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


@extend_schema(
    summary="Comptes d'un utilisateur",
    description="Récupère tous les comptes bancaires reliés au matricule d'un client au sein du réseau multi-banque."
)
class UserAccountsListView(APIView):
    """Récupère tous les comptes bancaires reliés au matricule d'un client."""
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