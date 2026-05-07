from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from decimal import Decimal
from .models import BankUser, Account, Transfer, Withdrawal


class BankUserTests(APITestCase):
    
    def setUp(self):
        self.client = APIClient()
        self.user_data = {
            'username': 'testuser',
            'email': 'testuser@example.com',
            'password': 'testpass123',
            'phone': '+237123456789'
        }
    
    def test_create_user(self):
        """Test creating a new user"""
        response = self.client.post('/api/users/', self.user_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(BankUser.objects.count(), 1)
        self.assertEqual(BankUser.objects.get().username, 'testuser')
        # Check that account was auto-created
        self.assertEqual(Account.objects.count(), 1)
    
    def test_list_users(self):
        """Test retrieving list of users"""
        BankUser.objects.create_user(**self.user_data)
        response = self.client.get('/api/users/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
    
    def test_get_user_detail(self):
        """Test retrieving a single user"""
        user = BankUser.objects.create_user(**self.user_data)
        response = self.client.get(f'/api/users/{user.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'testuser')
    
    def test_update_user(self):
        """Test updating a user"""
        user = BankUser.objects.create_user(**self.user_data)
        update_data = {'email': 'newemail@example.com', 'password': 'newpass123'}
        response = self.client.patch(f'/api/users/{user.id}/', update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertEqual(user.email, 'newemail@example.com')
    
    def test_delete_user(self):
        """Test deleting a user"""
        user = BankUser.objects.create_user(**self.user_data)
        response = self.client.delete(f'/api/users/{user.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(BankUser.objects.count(), 0)


class AccountTests(APITestCase):
    
    def setUp(self):
        self.client = APIClient()
        self.user1 = BankUser.objects.create_user(
            username='alice',
            email='alice@example.com',
            password='pass123'
        )
        self.user2 = BankUser.objects.create_user(
            username='bob',
            email='bob@example.com',
            password='pass123'
        )
    
    def test_account_auto_created(self):
        """Test that account is automatically created for new user"""
        self.assertTrue(hasattr(self.user1, 'account'))
        self.assertEqual(self.user1.account.balance, Decimal('500.00'))
    
    def test_list_accounts(self):
        """Test listing all accounts"""
        response = self.client.get('/api/accounts/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
    
    def test_get_account_by_id(self):
        """Test getting account by ID"""
        account = self.user1.account
        response = self.client.get(f'/api/accounts/{account.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'alice')
    
    def test_get_balance_by_username(self):
        """Test getting balance by username"""
        response = self.client.get('/api/accounts/balance/alice/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(Decimal(response.data['data']['balance']), Decimal('500.00'))
    
    def test_get_balance_nonexistent_user(self):
        """Test getting balance for non-existent user"""
        response = self.client.get('/api/accounts/balance/nonexistent/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data['status'], 'error')


class TransferTests(APITestCase):
    
    def setUp(self):
        self.client = APIClient()
        self.user1 = BankUser.objects.create_user(
            username='alice',
            email='alice@example.com',
            password='pass123'
        )
        self.user2 = BankUser.objects.create_user(
            username='bob',
            email='bob@example.com',
            password='pass123'
        )
        # Set initial balances
        self.user1.account.balance = Decimal('1000.00')
        self.user1.account.save()
        self.user2.account.balance = Decimal('500.00')
        self.user2.account.save()
    
    def test_successful_transfer(self):
        """Test successful transfer between accounts"""
        transfer_data = {
            'sender_username': 'alice',
            'receiver_username': 'bob',
            'amount': '200.00'
        }
        response = self.client.post('/api/transfers/', transfer_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'success')
        
        # Check balances updated correctly
        self.user1.account.refresh_from_db()
        self.user2.account.refresh_from_db()
        self.assertEqual(self.user1.account.balance, Decimal('800.00'))
        self.assertEqual(self.user2.account.balance, Decimal('700.00'))
    
    def test_transfer_insufficient_balance(self):
        """Test transfer with insufficient balance"""
        transfer_data = {
            'sender_username': 'alice',
            'receiver_username': 'bob',
            'amount': '2000.00'
        }
        response = self.client.post('/api/transfers/', transfer_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['status'], 'error')
        
        # Check balances unchanged
        self.user1.account.refresh_from_db()
        self.user2.account.refresh_from_db()
        self.assertEqual(self.user1.account.balance, Decimal('1000.00'))
        self.assertEqual(self.user2.account.balance, Decimal('500.00'))
    
    def test_transfer_nonexistent_sender(self):
        """Test transfer with non-existent sender"""
        transfer_data = {
            'sender_username': 'nonexistent',
            'receiver_username': 'bob',
            'amount': '100.00'
        }
        response = self.client.post('/api/transfers/', transfer_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_transfer_nonexistent_receiver(self):
        """Test transfer with non-existent receiver"""
        transfer_data = {
            'sender_username': 'alice',
            'receiver_username': 'nonexistent',
            'amount': '100.00'
        }
        response = self.client.post('/api/transfers/', transfer_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_list_transfers(self):
        """Test listing all transfers"""
        # Create a transfer first
        transfer_data = {
            'sender_username': 'alice',
            'receiver_username': 'bob',
            'amount': '100.00'
        }
        self.client.post('/api/transfers/', transfer_data, format='json')
        
        response = self.client.get('/api/transfers/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)


class WithdrawalTests(APITestCase):
    
    def setUp(self):
        self.client = APIClient()
        self.user = BankUser.objects.create_user(
            username='alice',
            email='alice@example.com',
            password='pass123'
        )
        # Set initial balance
        self.user.account.balance = Decimal('1000.00')
        self.user.account.save()
    
    def test_successful_withdrawal(self):
        """Test successful withdrawal"""
        withdrawal_data = {
            'username': 'alice',
            'amount': '300.00'
        }
        response = self.client.post('/api/withdrawals/', withdrawal_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'success')
        
        # Check balance updated correctly
        self.user.account.refresh_from_db()
        self.assertEqual(self.user.account.balance, Decimal('700.00'))
    
    def test_withdrawal_insufficient_balance(self):
        """Test withdrawal with insufficient balance"""
        withdrawal_data = {
            'username': 'alice',
            'amount': '2000.00'
        }
        response = self.client.post('/api/withdrawals/', withdrawal_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['status'], 'error')
        
        # Check balance unchanged
        self.user.account.refresh_from_db()
        self.assertEqual(self.user.account.balance, Decimal('1000.00'))
    
    def test_withdrawal_nonexistent_user(self):
        """Test withdrawal for non-existent user"""
        withdrawal_data = {
            'username': 'nonexistent',
            'amount': '100.00'
        }
        response = self.client.post('/api/withdrawals/', withdrawal_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_list_withdrawals(self):
        """Test listing all withdrawals"""
        # Create a withdrawal first
        withdrawal_data = {
            'username': 'alice',
            'amount': '100.00'
        }
        self.client.post('/api/withdrawals/', withdrawal_data, format='json')
        
        response = self.client.get('/api/withdrawals/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)


class ModelTests(TestCase):
    
    def setUp(self):
        self.user1 = BankUser.objects.create_user(
            username='alice',
            email='alice@example.com',
            password='pass123'
        )
        self.user2 = BankUser.objects.create_user(
            username='bob',
            email='bob@example.com',
            password='pass123'
        )
    
    def test_bank_user_str(self):
        """Test BankUser string representation"""
        self.assertEqual(str(self.user1), 'alice (customer)')
    
    def test_account_str(self):
        """Test Account string representation"""
        self.assertIn('alice', str(self.user1.account))
        self.assertIn('500.00', str(self.user1.account))
    
    def test_user_type_default(self):
        """Test that default user type is customer"""
        self.assertEqual(self.user1.user_type, BankUser.UserType.CUSTOMER)
    
    def test_account_initial_balance(self):
        """Test that new accounts start with 500.00"""
        self.assertEqual(self.user1.account.balance, Decimal('500.00'))