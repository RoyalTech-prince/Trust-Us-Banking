import jwt
from datetime import datetime, timedelta, timezone
from django.conf import settings
from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers

from .models import BankUser, Account, Bank, Deposit, Transfer, Withdrawal
from .serializers import (
    MultiBankLoginRequestSerializer,
    TransactionHistoryResponseSerializer,
    UniversalRegistrationSerializer, 
    BankEnrollmentSerializer,
    BankUserSerializer,
    TransferSerializer,
    WithdrawalSerializer,
    DepositSerializer,  # 👈 Added missing serializer import
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
    Includes the last 5 transactions for the targeted bank workspace.
    """

    @extend_schema(
        request=MultiBankLoginRequestSerializer,
        responses={200: serializers.Serializer},  # Keeps output generic
        summary="Authentification Multi-Banque",
        description="Permet à un utilisateur de se connecter au contexte spécifique d'une banque en utilisant son matricule/email et un mot de passe préfixé (ex: UBC_password ou MOMO_password)."
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

            # ─── EXTRACTION CONSOLIDÉE DES 5 DERNIÈRES TRANSACTIONS ───
            virements_envoyes = Transfer.objects.filter(sender=active_workspace_account)
            virements_recus = Transfer.objects.filter(receiver=active_workspace_account)
            retraits = Withdrawal.objects.filter(account=active_workspace_account)
            depots = Deposit.objects.filter(account=active_workspace_account)

            historique_combine = []

            for t in virements_envoyes:
                historique_combine.append({
                    'id': str(t.transaction_id),
                    'type': 'VIREMENT_EMIS',
                    'montant': float(t.amount),
                    'frais': float(t.fee),
                    'description': t.description or "Virement émis",
                    'date': t.timestamp.isoformat()
                })

            for t in virements_recus:
                historique_combine.append({
                    'id': str(t.transaction_id),
                    'type': 'VIREMENT_RECU',
                    'montant': float(t.amount),
                    'frais': 0.00,
                    'description': f"Virement reçu de {t.sender.owner.full_name}",
                    'date': t.timestamp.isoformat()
                })

            for r in retraits:
                historique_combine.append({
                    'id': str(r.transaction_id),
                    'type': 'RETRAIT',
                    'montant': float(r.amount),
                    'frais': float(r.fee),
                    'description': r.description or "Retrait de fonds",
                    'date': r.timestamp.isoformat()
                })

            for d in depots:
                historique_combine.append({
                    'id': str(d.transaction_id),
                    'type': 'DEPOT',
                    'montant': float(d.amount),
                    'frais': 0.00,
                    'description': d.description or "Dépôt Mobile Money",
                    'date': d.timestamp.isoformat()
                })

            # Tri par ordre chronologique décroissant (le plus récent en premier)
            historique_combine.sort(key=lambda x: x['date'], reverse=True)
            last_five_transactions = historique_combine[:5]
            # ──────────────────────────────────────────────────────────

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
                },
                "recent_transactions": last_five_transactions  # 👈 Intégration du nœud d'historique direct
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
    description="Crée un profil utilisateur universel, génère automatiquement un portefeuille Mobile Money centralisé et ouvre un compte dans la banque commerciale spécifiée."
)
class UniversalRegistrationView(generics.CreateAPIView):
    """Enregistre un profil utilisateur universel et initialise l'arborescence des portefeuilles liés."""
    serializer_class = UniversalRegistrationSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"message": "Utilisateur universel créé avec succès. Le portefeuille central Mobile Money (MOMO) a été initialisé automatiquement."}, 
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
    description="Exécute un virement financier entre deux comptes avec traitement atomique des soldes et application des frais de routage interbancaire."
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
    summary="Effectuer un retrait (Banque ➡️ Mobile Money)",
    description="Déduis les fonds du compte d'une banque commerciale classique (UBC, ECO...) et les transfère sur le portefeuille centralisé Mobile Money (MOMO). Applique un frais fixe de 50 FCFA."
)
class WithdrawalCreateView(APIView):
    """Traite le retrait d'un compte commercial pour alimenter le solde central Mobile Money."""
    def post(self, request):
        session = verify_web_session(request)
        if isinstance(session, str):
            return Response({"error": session}, status=status.HTTP_401_UNAUTHORIZED)

        serializer = WithdrawalSerializer(data=request.data)
        if serializer.is_valid():
            try:
                withdrawal = serializer.save()
                return Response({
                    "message": "Retrait effectué avec succès. Votre compte Mobile Money a été crédité.",
                    "transaction_id": str(withdrawal.transaction_id),
                    "amount": float(withdrawal.amount),
                    "fee": float(withdrawal.fee)
                }, status=status.HTTP_201_CREATED)
            except ValueError as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    summary="Effectuer un dépôt (Mobile Money ➡️ Banque)",
    description="Retire des fonds du portefeuille de transactions centralisé Mobile Money (MOMO) pour alimenter et recharger un compte bancaire commercial ciblé."
)
class DepositCreateView(APIView):
    """Traite le dépôt de fonds vers un compte commercial par prélèvement du solde Mobile Money."""
    def post(self, request):
        session = verify_web_session(request)
        if isinstance(session, str):
            return Response({"error": session}, status=status.HTTP_401_UNAUTHORIZED)

        serializer = DepositSerializer(data=request.data)
        if serializer.is_valid():
            try:
                deposit = serializer.save()
                return Response({
                    "message": "Dépôt validé avec succès. Votre compte commercial a été approvisionné.",
                    "transaction_id": str(deposit.transaction_id),
                    "amount": float(deposit.amount)
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
    description="Récupère tous les comptes bancaires (commerciaux et portefeuille MoMo) reliés au matricule d'un client au sein du réseau multi-banque."
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
    

class TransactionHistoryView(APIView):
    """
    Endpoint permettant de récupérer l'historique unifié et chronologique
    des transactions (Dépôts, Retraits, Virements) d'un compte bancaire.
    """

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="Authorization",
                type=str,
                location=OpenApiParameter.HEADER,
                description="Token JWT de session obtenu lors de la connexion (Format: Bearer <votre_token>)",
                required=True
            )
        ],
        responses={200: TransactionHistoryResponseSerializer(many=True)},
        summary="Historique des Transactions",
        description="Récupère l'historique complet, centralisé et trié par date pour le compte bancaire actif.",
        tags=["Historique des Transactions"]
    )
    def get(self, request):
        # 1. Extraction et validation du Token JWT depuis les en-têtes
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return Response(
                {"error": "Jeton d'authentification manquant dans les en-têtes."},
                status=status.HTTP_401_UNAUTHORIZED
            )

        try:
            token = auth_header.split(" ")[1] if " " in auth_header else auth_header
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            account_id = payload.get('account_id')
            matricule = payload.get('matricule')
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, IndexError):
            return Response(
                {"error": "Session expirée ou jeton de sécurité invalide."},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # 2. Vérification de l'existence du compte ciblé
        try:
            account = Account.objects.get(account_id=account_id)
        except Account.DoesNotExist:
            return Response(
                {"error": "Le compte bancaire rattaché à cette session est introuvable."},
                status=status.HTTP_404_NOT_FOUND
            )

        # 3. Collecte de toutes les transactions liées à ce compte
        virements_envoyes = Transfer.objects.filter(sender=account)
        virements_recus = Transfer.objects.filter(receiver=account)
        retraits = Withdrawal.objects.filter(account=account)
        depots = Deposit.objects.filter(account=account)

        # 4. Normalisation et consolidation des données en Français
        historique_unifie = []

        for t in virements_envoyes:
            historique_unifie.append({
                'transaction_id': t.transaction_id,
                'type_transaction': 'VIREMENT_EMIS',
                'matricule_utilisateur': matricule,
                'numero_compte': account.account_id,
                'amount': t.amount,
                'fee': t.fee,
                'description': t.description,
                'timestamp': t.timestamp
            })

        for t in virements_recus:
            historique_unifie.append({
                'transaction_id': t.transaction_id,
                'type_transaction': 'VIREMENT_RECU',
                'matricule_utilisateur': t.sender.owner.matricule,
                'numero_compte': account.account_id,
                'amount': t.amount,
                'fee': 0.00,
                'description': f"Virement reçu de {t.sender.owner.full_name}",
                'timestamp': t.timestamp
            })

        for r in retraits:
            historique_unifie.append({
                'transaction_id': r.transaction_id,
                'type_transaction': 'RETRAIT',
                'matricule_utilisateur': matricule,
                'numero_compte': account.account_id,
                'amount': r.amount,
                'fee': r.fee,
                'description': r.description,
                'timestamp': r.timestamp
            })

        for d in depots:
            historique_unifie.append({
                'transaction_id': d.transaction_id,
                'type_transaction': 'DEPOT',
                'matricule_utilisateur': matricule,
                'numero_compte': account.account_id,
                'amount': d.amount,
                'fee': 0.00,
                'description': d.description,
                'timestamp': d.timestamp
            })

        # 5. Tri chronologique (Du plus récent au plus ancien)
        historique_unifie.sort(key=lambda x: x['timestamp'], reverse=True)

        # 6. Sérialisation et retour de la réponse
        serializer = TransactionHistoryResponseSerializer(historique_unifie, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    

class TraceTransactionHistoryView(APIView):
    """
    Endpoint administratif permettant de tracer l'intégralité des flux 
    financiers de toutes les banques pour un utilisateur via son Matricule Unique.
    """

    @extend_schema(
        responses={200: TransactionHistoryResponseSerializer(many=True)},
        summary="Tracer l'Historique par Matricule",
        description="Recherche globale au sein du système de clearing pour extraire toutes les transactions liées au matricule spécifié.",
        tags=["Historique des Transactions"]
    )
    def get(self, request, matricule):
        # 1. Vérifier si l'utilisateur existe dans l'écosystème central
        try:
            user = BankUser.objects.get(matricule=matricule)
        except BankUser.DoesNotExist:
            return Response(
                {"error": f"Aucun utilisateur enregistré avec le matricule '{matricule}'."},
                status=status.HTTP_404_NOT_FOUND
            )

        # 2. Récupérer tous les comptes bancaires (UBC, Ecobank, etc.) possédés par cet utilisateur
        user_accounts = Account.objects.filter(owner=user)
        
        historique_trace = []

        # 3. Boucler sur chaque compte pour extraire et centraliser l'historique
        for account in user_accounts:
            virements_envoyes = Transfer.objects.filter(sender=account)
            virements_recus = Transfer.objects.filter(receiver=account)
            retraits = Withdrawal.objects.filter(account=account)
            depots = Deposit.objects.filter(account=account)

            # Normalisation des flux émis
            for t in virements_envoyes:
                historique_trace.append({
                    'transaction_id': t.transaction_id,
                    'type_transaction': 'VIREMENT_EMIS',
                    'matricule_utilisateur': user.matricule,
                    'numero_compte': account.account_id,
                    'amount': t.amount,
                    'fee': t.fee,
                    'description': f"[{account.bank.code}] {t.description}",
                    'timestamp': t.timestamp
                })

            # Normalisation des flux reçus
            for t in virements_recus:
                historique_trace.append({
                    'transaction_id': t.transaction_id,
                    'type_transaction': 'VIREMENT_RECU',
                    'matricule_utilisateur': t.sender.owner.matricule,
                    'numero_compte': account.account_id,
                    'amount': t.amount,
                    'fee': 0.00,
                    'description': f"[{account.bank.code}] Virement reçu de {t.sender.owner.full_name}",
                    'timestamp': t.timestamp
                })

            # Normalisation des retraits
            for r in retraits:
                historique_trace.append({
                    'transaction_id': r.transaction_id,
                    'type_transaction': 'RETRAIT',
                    'matricule_utilisateur': user.matricule,
                    'numero_compte': account.account_id,
                    'amount': r.amount,
                    'fee': r.fee,
                    'description': f"[{account.bank.code}] {r.description}",
                    'timestamp': r.timestamp
                })

            # Normalisation des dépôts
            for d in depots:
                historique_trace.append({
                    'transaction_id': d.transaction_id,
                    'type_transaction': 'DEPOT',
                    'matricule_utilisateur': user.matricule,
                    'numero_compte': account.account_id,
                    'amount': d.amount,
                    'fee': 0.00,
                    'description': f"[{account.bank.code}] {d.description}",
                    'timestamp': d.timestamp
                })

        # 4. Tri par ordre chronologique décroissant (le plus récent en premier)
        historique_trace.sort(key=lambda x: x['timestamp'], reverse=True)

        # 5. Sérialisation
        serializer = TransactionHistoryResponseSerializer(historique_trace, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class LocalAccountBalanceView(APIView):
    """
    Permet de consulter rapidement le solde et le numéro de téléphone 
    d'un compte local à partir du matricule de l'utilisateur.
    """

    @extend_schema(
        summary="Consultation du solde local par Matricule",
        description="Retourne le numéro de téléphone et le solde du compte d'un utilisateur pour la banque du contexte actuel."
    )
    def get(self, request, matricule):
        # 1. Récupérer l'utilisateur par son matricule
        user_profile = BankUser.objects.filter(matricule=matricule).first()
        if not user_profile:
            return Response(
                {"error": f"Aucun utilisateur trouvé avec le matricule {matricule}."}, 
                status=status.HTTP_404_NOT_FOUND
            )

        # 2. Identifier la banque du contexte actuel.
        # On peut la récupérer depuis le token de session JWT (request.user ou active_bank passée en query param/header)
        # Ici, on suppose que vous filtrez sur la banque active reçue en paramètre ou via l'en-tête, 
        # ou à défaut, le premier compte bancaire trouvé.
        target_bank_code = request.headers.get('X-Bank-Context') or request.query_params.get('bank_code')
        
        account_query = Account.objects.filter(owner=user_profile)
        if target_bank_code:
            account_query = account_query.filter(bank__code=target_bank_code)
            
        active_account = account_query.first()

        if not active_account:
            return Response(
                {"error": f"Aucun compte bancaire configuré pour ce matricule dans le contexte demandé."}, 
                status=status.HTTP_404_NOT_FOUND
            )

        # 3. Renvoyer STRICTEMENT le numéro de mobile et le solde
        return Response({
            "mobile_number": user_profile.phone_number,  # Récupère le champ téléphone du modèle BankUser
            "balance": float(active_account.balance)
        }, status=status.HTTP_200_OK)