from rest_framework import serializers
from django.core.mail import send_mail
from django.conf import settings
from .models import BankUser, Account, Bank, Transfer, Withdrawal, Deposit

# ─── 1. CORE MODELS SERIALIZERS ───

class BankSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bank
        fields = ['name', 'code']

class AccountSerializer(serializers.ModelSerializer):
    bank = BankSerializer(read_only=True)
    class Meta:
        model = Account
        fields = ['account_id', 'bank', 'balance', 'created_at']

# ─── 2. UNIVERSAL REGISTRATION (The "Identity" Serializer) ───

class UniversalRegistrationSerializer(serializers.ModelSerializer):
    bank_code = serializers.CharField(write_only=True, help_text="e.g., UBC, AFB, or ECO")
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    class Meta:
        model = BankUser
        fields = ['matricule', 'full_name', 'email', 'phone', 'user_type', 'bank_code', 'password']
        read_only_fields = ['matricule']

    def validate(self, data):
        bank_code = data.get('bank_code')
        password = data.get('password')

        try:
            target_bank = Bank.objects.get(code=bank_code)
        except Bank.DoesNotExist:
            raise serializers.ValidationError({
                "bank_code": "Cette banque n'existe pas dans notre écosystème."
            })

        expected_prefix = f"{bank_code}_"
        if not password.startswith(expected_prefix):
            raise serializers.ValidationError({
                "password": f"Contrainte d'architecture réseau : Pour ouvrir un compte chez {target_bank.name}, votre mot de passe doit obligatoirement commencer par le préfixe '{expected_prefix}'."
            })

        data['target_bank_object'] = target_bank
        return data

    def create(self, validated_data):
        target_bank = validated_data.pop('target_bank_object')
        validated_data.pop('bank_code')
        raw_password = validated_data.pop('password')

        # 1. Create the Global Core Identity profile (Automated MoMo initialization triggers inside model save)
        user = BankUser(
            full_name=validated_data['full_name'],
            email=validated_data['email'],
            phone=validated_data['phone'],
            user_type=validated_data['user_type']
        )
        user.set_password(raw_password)
        user.save() 

        # 2. CREATE THE FIRST COMMERCIAL LEDGER CHECKING ACCOUNT ROW
        new_account = Account.objects.create(
            owner=user,
            bank=target_bank,
            password=user.password  # Synchronizes credentials safely
        )
        
        # 3. SEND ONBOARDING EMAIL NOTIFICATION
        try:
            email_subject = f"Bienvenue chez Trust-Us-Banking ! Votre Matricule Unique : {user.matricule}"
            email_body = (
                f"Bonjour {user.full_name},\n\n"
                f"Félicitations ! Votre profil d'identité universel a été configuré avec succès.\n\n"
                f"Voici vos informations de centralisation :\n"
                f"▪️ Matricule Unique : {user.matricule}\n"
                f"▪️ Banque Principale : {target_bank.name} ({target_bank.code})\n"
                f"▪️ Numéro de Compte : {new_account.account_id}\n\n"
                f"Votre portefeuille d'échange central Mobile Money (MOMO) a également été créé automatiquement et crédité d'un solde de test.\n\n"
                f"Pour vous connecter à votre espace, utilisez votre matricule et votre mot de passe "
                f"commençant par le préfixe de votre banque (Ex: {target_bank.code}_...).\n\n"
                f"Merci de faire confiance à notre réseau décentralisé.\n"
            )
            send_mail(
                subject=email_subject,
                message=email_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False
            )
        except Exception as e:
            print(f"❌ SMTP Error encountered: {str(e)}")
            pass 

        return user


class BankEnrollmentSerializer(serializers.Serializer):
    matricule = serializers.CharField()
    bank_code = serializers.CharField()
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    
    account_id = serializers.CharField(read_only=True)
    full_name = serializers.CharField(read_only=True)

    def validate(self, data):
        bank_code = data.get('bank_code')
        password = data.get('password')

        try:
            user = BankUser.objects.get(matricule=data['matricule'])
            bank = Bank.objects.get(code=bank_code)
        except (BankUser.DoesNotExist, Bank.DoesNotExist):
            raise serializers.ValidationError(
                "Utilisateur ou Banque introuvable dans l'écosystème global."
            )

        if Account.objects.filter(owner=user, bank=bank).exists():
            raise serializers.ValidationError(
                f"Erreur : Cet utilisateur possède déjà un compte actif chez {bank.name}."
            )

        expected_prefix = f"{bank_code}_"
        if not password.startswith(expected_prefix):
            raise serializers.ValidationError({
                "password": f"Erreur d'aiguillage : Le mot de passe de ce nouveau compte doit obligatoirement commencer par '{expected_prefix}' pour correspondre à la banque choisie."
            })

        data['user_object'] = user
        data['bank_object'] = bank
        return data

    def create(self, validated_data):
        user = validated_data['user_object']
        bank = validated_data['bank_object']

        account = Account.objects.create(
            owner=user,
            bank=bank,
            password=user.password
        )

        try:
            email_subject = f"Ouverture de Compte Confirmée - {bank.code}"
            email_body = (
                f"Bonjour {user.full_name},\n\n"
                f"Nous vous confirmons l'ouverture réussie de votre compte bancaire.\n\n"
                f"Détails de l'inscription :\n"
                f"▪️ Matricule Référence : {user.matricule}\n"
                f"▪️ Nouvelle Institution : {bank.name} ({bank.code})\n"
                f"▪️ Identifiant Unique du Compte : {account.account_id}\n\n"
                f"Pour gérer ce nouvel espace de travail, connectez-vous en utilisant le préfixe dédié : {bank.code}_...\n\n"
                f"Cordialement,\n"
            )
            send_mail(
                subject=email_subject,
                message=email_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False
            )
        except Exception as e:
            print(f"❌ Enrollment SMTP Error: {str(e)}")
            pass

        user.account_id = account.account_id
        return user


class MultiBankLoginRequestSerializer(serializers.Serializer):
    identifier = serializers.CharField(
        required=True,
        help_text="Votre adresse email ou Matricule Unique (Ex: RT20260001)"
    )
    password = serializers.CharField(
        required=True,
        style={'input_type': 'password'},
        help_text="Mot de passe préfixé par le code de la banque (Ex: UBC_monMotDePasse ou MOMO_monMotDePasse)"
    )


# ─── 3. TRANSACTION DATA LINKERS ───

class AccountInfoSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source='owner.full_name', read_only=True)
    bank_name = serializers.CharField(source='bank.name', read_only=True)
    bank_code = serializers.CharField(source='bank.code', read_only=True)

    class Meta:
        model = Account
        fields = ['account_id', 'owner_name', 'bank_name', 'bank_code']


class TransferSerializer(serializers.ModelSerializer):
    sender_account_id = serializers.UUIDField(write_only=True)
    receiver_matricule = serializers.CharField(write_only=True)
    receiver_bank_code = serializers.CharField(write_only=True)
    
    sender_details = AccountInfoSerializer(source='sender', read_only=True)
    receiver_details = AccountInfoSerializer(source='receiver', read_only=True)
    
    class Meta:
        model = Transfer
        fields = [
            'transaction_id', 'amount', 'fee', 'timestamp', 'description',
            'sender_account_id', 'receiver_matricule', 'receiver_bank_code',
            'sender_details', 'receiver_details'
        ]
        read_only_fields = ['transaction_id', 'timestamp', 'fee', 'sender_details', 'receiver_details']
    
    def create(self, validated_data):
        sender_id = validated_data.pop('sender_account_id')
        rec_mat = validated_data.pop('receiver_matricule')
        rec_code = validated_data.pop('receiver_bank_code')
        amount = validated_data.get('amount')
        description = validated_data.get('description', None)

        try:
            sender_acc = Account.objects.get(account_id=sender_id)
            receiver_acc = Account.objects.get(owner__matricule=rec_mat, bank__code=rec_code)
        except Account.DoesNotExist:
            raise serializers.ValidationError("Compte émetteur ou bénéficiaire introuvable au sein du réseau interbancaire.")
        
        transfer = Transfer(
            sender=sender_acc,
            receiver=receiver_acc,
            amount=amount,
            description=description
        )
        
        try:
            transfer.save() 
            return transfer
        except ValueError as e:
            raise serializers.ValidationError(str(e))


class WithdrawalSerializer(serializers.ModelSerializer):
    """
    Serializer pour alimenter son compte Mobile Money depuis son compte bancaire commercial (Retrait).
    """
    account_id = serializers.UUIDField(write_only=True, help_text="ID du compte bancaire commercial à débiter.")
    
    class Meta:
        model = Withdrawal
        fields = ['transaction_id', 'amount', 'fee', 'timestamp', 'description', 'account_id']
        read_only_fields = ['transaction_id', 'timestamp', 'fee']
    
    def create(self, validated_data):
        acc_id = validated_data.pop('account_id')
        amount = validated_data.get('amount')
        description = validated_data.get('description', None)

        try:
            account = Account.objects.get(account_id=acc_id)
        except Account.DoesNotExist:
            raise serializers.ValidationError("Compte bancaire spécifié introuvable.")
        
        if account.bank.code == 'MOMO':
            raise serializers.ValidationError("Opération invalide : Vous ne pouvez pas effectuer un retrait bancaire directement depuis le hub Mobile Money.")

        withdrawal = Withdrawal(account=account, amount=amount, description=description)
        
        try:
            withdrawal.save()
            return withdrawal
        except ValueError as e:
            raise serializers.ValidationError(str(e))


class DepositSerializer(serializers.ModelSerializer):
    """
    Serializer pour envoyer des fonds depuis son compte Mobile Money vers son compte bancaire commercial (Dépôt).
    """
    account_id = serializers.UUIDField(write_only=True, help_text="ID du compte bancaire commercial cible à créditer.")

    class Meta:
        model = Deposit
        fields = ['transaction_id', 'amount', 'timestamp', 'description', 'account_id']
        read_only_fields = ['transaction_id', 'timestamp']

    def create(self, validated_data):
        acc_id = validated_data.pop('account_id')
        amount = validated_data.get('amount')
        description = validated_data.get('description', None)

        try:
            account = Account.objects.get(account_id=acc_id)
        except Account.DoesNotExist:
            raise serializers.ValidationError("Compte bancaire de destination introuvable.")

        if account.bank.code == 'MOMO':
            raise serializers.ValidationError("Opération invalide : Pour recharger votre solde Mobile Money, effectuez un Retrait depuis une banque commerciale.")

        deposit = Deposit(account=account, amount=amount, description=description)

        try:
            deposit.save()
            return deposit
        except ValueError as e:
            raise serializers.ValidationError(str(e))


class AccountBalanceSerializer(serializers.ModelSerializer):
    bank_name = serializers.CharField(source='bank.name', read_only=True)
    owner_name = serializers.CharField(source='owner.full_name', read_only=True)
    matricule = serializers.CharField(source='owner.matricule', read_only=True)
    
    class Meta:
        model = Account
        fields = ['account_id', 'owner_name', 'matricule', 'bank_name', 'balance', 'created_at']


class BankUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankUser
        fields = ['matricule', 'full_name', 'email', 'phone', 'user_type', 'created_at']
        read_only_fields = ['matricule', 'created_at']

    def update(self, instance, validated_data):
        instance.email = validated_data.get('email', instance.email)
        instance.phone = validated_data.get('phone', instance.phone)
        instance.full_name = validated_data.get('full_name', instance.full_name)
        instance.save()
        return instance


class TransactionHistoryResponseSerializer(serializers.Serializer):
    id_transaction = serializers.UUIDField(source='transaction_id')
    type_transaction = serializers.CharField()
    matricule_utilisateur = serializers.CharField()
    numero_compte = serializers.UUIDField()
    montant = serializers.DecimalField(max_digits=12, decimal_places=2)
    frais = serializers.DecimalField(max_digits=10, decimal_places=2)
    details = serializers.CharField(source='description')
    date_creation = serializers.DateTimeField(source='timestamp')