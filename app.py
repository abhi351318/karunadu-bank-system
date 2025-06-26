from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import os
from functools import wraps
import random
import string

app = Flask(__name__)

# --- Configuration ---
# Use environment variable for database URI, with a fallback for local development
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///bank.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a_very_secret_key_that_is_hard_to_guess')

db = SQLAlchemy(app)

# --- Database Models ---
class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200))
    contact_info = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

    accounts = db.relationship('Account', backref='customer', lazy=True, cascade="all, delete-orphan") # Added cascade for deletion
    loans = db.relationship('Loan', backref='customer', lazy=True, cascade="all, delete-orphan") # Added cascade for deletion

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<Customer {self.name}>"

class Account(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    account_number = db.Column(db.String(20), unique=True, nullable=False)
    account_type = db.Column(db.String(50), nullable=False)
    balance = db.Column(db.Float, default=0.0)
    opening_date = db.Column(db.DateTime, default=datetime.utcnow)

    transactions = db.relationship('Transaction', backref='account', lazy=True, foreign_keys='[Transaction.account_id]', cascade="all, delete-orphan") # Added cascade
    outgoing_transfers = db.relationship('Transaction', backref='target_account', lazy=True, foreign_keys='[Transaction.target_account_id]')


    def __repr__(self):
        return f"<Account {self.account_number}>"

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=False)
    transaction_type = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.String(200))
    target_account_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=True)

    def __repr__(self):
        return f"<Transaction {self.transaction_type} on {self.date}>"

class Loan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=False)
    loan_amount = db.Column(db.Float, nullable=False)
    interest_rate = db.Column(db.Float, nullable=False)
    term_months = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(50), default='Pending', nullable=False)
    application_date = db.Column(db.DateTime, default=datetime.utcnow)
    approval_date = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f"<Loan {self.id} - {self.status}>"

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<Admin {self.username}>"

# --- Helper function to require admin login ---
def admin_login_required(view_func):
    @wraps(view_func)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            flash('Please log in to access the admin panel.', 'warning')
            return redirect(url_for('admin_login'))
        return view_func(*args, **kwargs)
    return decorated_function

# --- Helper function to require customer login ---
def customer_login_required(view_func):
    @wraps(view_func)
    def decorated_function(*args, **kwargs):
        if 'customer_id' not in session:
            flash('Please log in to access your account.', 'warning')
            return redirect(url_for('customer_login'))
        return view_func(*args, **kwargs)
    return decorated_function


# --- Flask Routes ---

@app.route('/')
def index():
    if 'customer_id' in session:
         return redirect(url_for('customer_dashboard'))
    if 'admin_id' in session:
        return redirect(url_for('admin_dashboard'))

    return render_template('index.html')

# --- Admin Routes ---

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if 'admin_id' in session:
        flash('You are already logged in as Admin.', 'info')
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        admin = Admin.query.filter_by(username=username).first()

        if admin and admin.check_password(password):
            session['admin_id'] = admin.id
            flash('Logged in successfully!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid username or password.', 'danger')

    return render_template('admin_login.html')

@app.route('/admin/dashboard')
@admin_login_required
def admin_dashboard():
    total_customers = Customer.query.count()
    total_accounts = Account.query.count()
    latest_transactions = Transaction.query.order_by(Transaction.date.desc()).limit(10).all()
    pending_loans_count = Loan.query.filter_by(status='Pending').count()

    return render_template('admin_dashboard.html',
                           total_customers=total_customers,
                           total_accounts=total_accounts,
                           latest_transactions=latest_transactions,
                           pending_loans_count=pending_loans_count)


@app.route('/admin/logout')
@admin_login_required
def admin_logout():
    session.pop('admin_id', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('admin_login'))

# --- Admin Routes for Customer Management ---

@app.route('/admin/customers')
@admin_login_required
def admin_view_customers():
    customers = Customer.query.order_by(Customer.id).all() # Order by ID for consistency
    return render_template('admin_customers.html', customers=customers)

@app.route('/admin/customer/<int:customer_id>')
@admin_login_required
def admin_view_customer_details(customer_id):
    customer = Customer.query.get_or_404(customer_id)

    customer_accounts = customer.accounts
    customer_loans = customer.loans

    account_ids = [acc.id for acc in customer_accounts]
    customer_transactions = []
    if account_ids:
        customer_transactions = Transaction.query.filter(Transaction.account_id.in_(account_ids)).order_by(Transaction.date.desc()).all()

    return render_template('admin_customer_details.html',
                           customer=customer,
                           customer_accounts=customer_accounts,
                           customer_loans=customer_loans,
                           customer_transactions=customer_transactions)

# --- Admin Route for Editing Specific Customer Details ---
@app.route('/admin/customer/<int:customer_id>/edit', methods=['GET', 'POST'])
@admin_login_required
def admin_edit_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)

    if request.method == 'POST':
        # Get updated data from the form
        customer.name = request.form.get('name')
        customer.address = request.form.get('address')
        customer.contact_info = request.form.get('contact_info')
        # NOTE: Password is NOT edited here. A separate password reset mechanism would be needed.

        # Basic Validation
        if not customer.name or not customer.contact_info:
            flash('Name and Contact Info are required.', 'danger')
            # Pass back form data and customer object to repopulate the form
            return render_template('admin_edit_customer.html', customer=customer, form_data=request.form)

        # Check if the updated contact_info is already taken by *another* customer
        existing_customer_with_contact = Customer.query.filter_by(contact_info=customer.contact_info).first()
        if existing_customer_with_contact and existing_customer_with_contact.id != customer.id:
             flash('This contact info is already used by another customer.', 'danger')
             # Pass back form data and customer object
             return render_template('admin_edit_customer.html', customer=customer, form_data=request.form)


        try:
            db.session.commit() # Commit changes to the database
            flash(f'Customer "{customer.name}" details updated successfully!', 'success')
            return redirect(url_for('admin_view_customer_details', customer_id=customer.id)) # Redirect to the customer's detail page
        except Exception as e:
            db.session.rollback() # Rollback in case of error
            flash(f'Error updating customer: {str(e)}', 'danger')
            print(f"Error updating customer: {e}")
            # Pass back form data and customer object
            return render_template('admin_edit_customer.html', customer=customer, form_data=request.form)


    # For GET request, render the edit form with current customer data
    return render_template('admin_edit_customer.html', customer=customer, form_data=customer.__dict__) # Pass customer data as form_data


# --- Admin Route for Deleting Specific Customer ---
@app.route('/admin/customer/<int:customer_id>/delete', methods=['POST'])
@admin_login_required
def admin_delete_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)

    try:
        # Check if the customer has accounts with non-zero balance or active loans
        # In a real bank, you'd prevent deletion or transfer funds/loans first
        # For simplicity here, we use cascade="all, delete-orphan" in models,
        # which will delete associated accounts, loans, and transactions automatically.
        # Be EXTREMELY cautious with real data and cascade delete!

        db.session.delete(customer) # Mark the customer for deletion
        db.session.commit() # Commit the deletion

        flash(f'Customer "{customer.name}" and all associated data deleted successfully.', 'success')
        return redirect(url_for('admin_view_customers')) # Redirect back to the customer list

    except Exception as e:
        db.session.rollback() # Rollback in case of error
        flash(f'Error deleting customer: {str(e)}', 'danger')
        print(f"Error deleting customer: {e}")
        # Redirect back to the customer list or details page
        return redirect(url_for('admin_view_customer_details', customer_id=customer.id))


@app.route('/admin/add_customer', methods=['GET', 'POST'])
@admin_login_required
def admin_add_customer():
    if request.method == 'POST':
        name = request.form.get('name')
        address = request.form.get('address')
        contact_info = request.form.get('contact_info')

        if not name or not contact_info:
            flash('Name and Contact Info are required.', 'danger')
            return redirect(url_for('admin_add_customer'))

        existing_customer = Customer.query.filter_by(contact_info=contact_info).first()
        if existing_customer:
            flash('A customer with this contact info already exists. They can use the registration page to create an account.', 'danger')
            return redirect(url_for('admin_add_customer'))

        new_customer = Customer(name=name, address=address, contact_info=contact_info)

        db.session.add(new_customer)

        try:
            db.session.commit()
            flash(f'Customer "{name}" added successfully! They can now register for an account.', 'success')
            return redirect(url_for('admin_view_customers'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding customer: {str(e)}', 'danger')
            print(f"Error adding customer: {e}")
            return redirect(url_for('admin_add_customer'))

    return render_template('admin_add_customer.html')


# --- Admin Route for Transaction Management ---
@app.route('/admin/transactions')
@admin_login_required
def admin_view_transactions():
    transactions = Transaction.query.order_by(Transaction.date.desc()).all()
    return render_template('admin_transactions.html', transactions=transactions)

# --- Admin Route for Account Management ---
@app.route('/admin/accounts')
@admin_login_required
def admin_view_accounts():
    accounts = Account.query.order_by(Account.account_number).all()
    return render_template('admin_accounts.html', accounts=accounts)

# --- Admin Routes for Loan Management ---
@app.route('/admin/loans')
@admin_login_required
def admin_view_loans():
    loans = Loan.query.order_by(Loan.application_date.desc()).all()
    return render_template('admin_loans.html', loans=loans)

@app.route('/admin/loan/<int:loan_id>')
@admin_login_required
def admin_view_loan_details(loan_id):
    loan = Loan.query.get_or_404(loan_id)
    return render_template('admin_loan_details.html', loan=loan)


@app.route('/admin/loan/<int:loan_id>/approve', methods=['POST'])
@admin_login_required
def admin_approve_loan(loan_id):
    loan = Loan.query.get_or_404(loan_id)

    if loan.status == 'Pending':
        try:
            loan.status = 'Approved'
            loan.approval_date = datetime.utcnow()

            account = Account.query.get(loan.account_id)
            if account:
                account.balance += loan.loan_amount

                new_transaction = Transaction(
                    account_id=account.id,
                    transaction_type='Loan Disbursement',
                    amount=loan.loan_amount,
                    description=f'Loan #{loan.id} disbursed'
                )
                db.session.add(new_transaction)
            else:
                 flash(f'Account for loan #{loan.id} not found!', 'danger')
                 db.session.rollback()
                 return redirect(url_for('admin_view_loan_details', loan_id=loan.id))


            db.session.commit()
            flash(f'Loan #{loan.id} approved and disbursed successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error approving loan: {str(e)}', 'danger')
            print(f"Error approving loan: {e}")
    elif loan.status == 'Approved':
         flash(f'Loan #{loan.id} is already approved.', 'info')
    else:
         flash(f'Loan #{loan.id} has status "{loan.status}" and cannot be approved.', 'warning')


    return redirect(url_for('admin_view_loan_details', loan_id=loan.id))


@app.route('/admin/loan/<int:loan_id>/reject', methods=['POST'])
@admin_login_required
def admin_reject_loan(loan_id):
    loan = Loan.query.get_or_404(loan_id)

    if loan.status == 'Pending':
        try:
            loan.status = 'Rejected'
            loan.approval_date = datetime.utcnow()
            db.session.commit()
            flash(f'Loan #{loan.id} rejected.', 'warning')
        except Exception as e:
            db.session.rollback()
            flash(f'Error rejecting loan: {str(e)}', 'danger')
            print(f"Error rejecting loan: {e}")
    else:
         flash(f'Loan #{loan.id} has status "{loan.status}" and cannot be rejected.', 'warning')

    return redirect(url_for('admin_view_loan_details', loan_id=loan.id))


# --- Admin Route for Reporting (Placeholder) ---
@app.route('/admin/reports')
@admin_login_required
def admin_reports():
    # Keeping this as a placeholder for complex reporting
    flash("Reporting feature is not fully implemented.", 'info')
    return render_template('admin_reports.html')


# --- Customer Routes ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'customer_id' in session:
        flash('You are already logged in.', 'info')
        return redirect(url_for('customer_dashboard'))

    if request.method == 'POST':
        name = request.form.get('name')
        address = request.form.get('address')
        contact_info = request.form.get('contact_info')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        account_type = request.form.get('account_type')

        if not name or not contact_info or not password or not confirm_password or not account_type:
            flash('All fields are required.', 'danger')
            return render_template('register.html', form_data=request.form)

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('register.html', form_data=request.form)

        existing_customer = Customer.query.filter_by(contact_info=contact_info).first()
        if existing_customer:
            flash('A customer with this contact info already exists. Please log in or use a different contact.', 'danger')
            return render_template('register.html', form_data=request.form)

        new_customer = Customer(name=name, address=address, contact_info=contact_info)
        new_customer.set_password(password)

        db.session.add(new_customer)

        try:
            db.session.commit()

            account_number = str(random.randint(1000000000, 9999999999))
            existing_account = Account.query.filter_by(account_number=account_number).first()
            while existing_account:
                 account_number = str(random.randint(1000000000, 9999999999))
                 existing_account = Account.query.filter_by(account_number=account_number).first()


            new_account = Account(
                customer_id=new_customer.id,
                account_number=account_number,
                account_type=account_type,
                balance=0.0
            )

            db.session.add(new_account)
            db.session.commit()

            flash('Registration successful! Please log in with your contact info and password.', 'success')
            return redirect(url_for('customer_login'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error during registration: {str(e)}', 'danger')
            print(f"Error during registration: {e}")
            return render_template('register.html', form_data=request.form)

    return render_template('register.html', form_data={})


@app.route('/login', methods=['GET', 'POST'])
def customer_login():
    if 'customer_id' in session:
        flash('You are already logged in.', 'info')
        return redirect(url_for('customer_dashboard'))

    if request.method == 'POST':
        contact_info = request.form.get('contact_info')
        password = request.form.get('password')

        customer = Customer.query.filter_by(contact_info=contact_info).first()

        if customer and customer.check_password(password):
            session['customer_id'] = customer.id
            flash('Logged in successfully!', 'success')
            return redirect(url_for('customer_dashboard'))
        else:
            flash('Invalid contact info or password.', 'danger')

    return render_template('customer_login.html')


@app.route('/dashboard')
@customer_login_required
