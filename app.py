# --- Customer Authentication ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'customer_id' in session:
        return redirect(url_for('customer_dashboard'))

    if request.method == 'POST':
        name = request.form['name']
        address = request.form['address']
        contact_info = request.form['contact_info']
        password = request.form['password']
        account_type = request.form['account_type']

        if not name or not contact_info or not password or not account_type:
            flash('All fields are required.', 'danger')
            return redirect(url_for('register'))

        existing = Customer.query.filter_by(contact_info=contact_info).first()
        if existing:
            flash('Customer already exists.', 'danger')
            return redirect(url_for('register'))

        customer = Customer(name=name, address=address, contact_info=contact_info)
        customer.set_password(password)
        db.session.add(customer)
        db.session.commit()

        account_number = str(random.randint(1000000000, 9999999999))
        account = Account(customer_id=customer.id, account_number=account_number, account_type=account_type)
        db.session.add(account)
        db.session.commit()

        flash('Registration successful!', 'success')
        return redirect(url_for('customer_login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def customer_login():
    if 'customer_id' in session:
        return redirect(url_for('customer_dashboard'))

    if request.method == 'POST':
        contact_info = request.form['contact_info']
        password = request.form['password']

        customer = Customer.query.filter_by(contact_info=contact_info).first()
        if customer and customer.check_password(password):
            session['customer_id'] = customer.id
            flash('Logged in!', 'success')
            return redirect(url_for('customer_dashboard'))
        else:
            flash('Invalid credentials.', 'danger')

    return render_template('customer_login.html')

@app.route('/logout')
def customer_logout():
    session.pop('customer_id', None)
    flash('Logged out.', 'info')
    return redirect(url_for('customer_login'))

# --- Customer Dashboard ---
@app.route('/dashboard')
@customer_login_required
def customer_dashboard():
    customer = Customer.query.get(session['customer_id'])
    return render_template('customer_dashboard.html', customer=customer)

# --- Banking Operations ---
@app.route('/deposit/<int:account_id>', methods=['GET', 'POST'])
@customer_login_required
def deposit(account_id):
    account = Account.query.get_or_404(account_id)

    if request.method == 'POST':
        amount = float(request.form['amount'])
        if amount <= 0:
            flash('Invalid amount.', 'danger')
        else:
            account.balance += amount
            tx = Transaction(account_id=account.id, transaction_type='Deposit', amount=amount, description='Deposit')
            db.session.add(tx)
            db.session.commit()
            flash('Deposit successful.', 'success')
            return redirect(url_for('customer_dashboard'))

    return render_template('customer_deposit.html', account=account)

@app.route('/withdraw/<int:account_id>', methods=['GET', 'POST'])
@customer_login_required
def withdraw(account_id):
    account = Account.query.get_or_404(account_id)

    if request.method == 'POST':
        amount = float(request.form['amount'])
        if amount <= 0 or amount > account.balance:
            flash('Invalid amount.', 'danger')
        else:
            account.balance -= amount
            tx = Transaction(account_id=account.id, transaction_type='Withdrawal', amount=amount, description='Withdrawal')
            db.session.add(tx)
            db.session.commit()
            flash('Withdrawal successful.', 'success')
            return redirect(url_for('customer_dashboard'))

    return render_template('customer_withdraw.html', account=account)

@app.route('/transfer/<int:account_id>', methods=['GET', 'POST'])
@customer_login_required
def transfer(account_id):
    source = Account.query.get_or_404(account_id)

    if request.method == 'POST':
        target_acc_num = request.form['target_account']
        amount = float(request.form['amount'])

        target = Account.query.filter_by(account_number=target_acc_num).first()

        if not target or target.id == source.id:
            flash('Invalid target account.', 'danger')
        elif amount <= 0 or amount > source.balance:
            flash('Invalid amount.', 'danger')
        else:
            source.balance -= amount
            target.balance += amount

            tx1 = Transaction(account_id=source.id, transaction_type='Transfer (Out)', amount=amount, target_account_id=target.id, description='Transfer to another account')
            tx2 = Transaction(account_id=target.id, transaction_type='Transfer (In)', amount=amount, target_account_id=source.id, description='Transfer from another account')

            db.session.add_all([tx1, tx2])
            db.session.commit()
            flash('Transfer successful.', 'success')
            return redirect(url_for('customer_dashboard'))

    return render_template('customer_transfer.html', account=source)

# --- Loan Application ---
@app.route('/loan/apply', methods=['GET', 'POST'])
@customer_login_required
def apply_loan():
    customer = Customer.query.get(session['customer_id'])
    if request.method == 'POST':
        amount = float(request.form['amount'])
        rate = float(request.form['rate'])
        term = int(request.form['term'])
        account_id = int(request.form['account_id'])

        loan = Loan(customer_id=customer.id, account_id=account_id, loan_amount=amount, interest_rate=rate, term_months=term)
        db.session.add(loan)
        db.session.commit()
        flash('Loan application submitted.', 'success')
        return redirect(url_for('customer_dashboard'))

    return render_template('customer_apply_loan.html', accounts=customer.accounts)

# --- Initialize DB and Admin ---
with app.app_context():
    db.create_all()
    if not Admin.query.first():
        default_admin = Admin(username="admin")
        default_admin.set_password("admin123")
        db.session.add(default_admin)
        db.session.commit()

# --- Run App for Render ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)