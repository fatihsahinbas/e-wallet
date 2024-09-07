import streamlit as st
import uuid
import sqlite3
import pandas as pd
from datetime import datetime
import plotly.express as px

# Database setup
conn = sqlite3.connect("ewallet.db", check_same_thread=False)
c = conn.cursor()

# Create tables if they don't exist
c.execute(
    """CREATE TABLE IF NOT EXISTS users
             (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, wallet_id TEXT, balance REAL)"""
)
c.execute(
    """CREATE TABLE IF NOT EXISTS transactions
             (id INTEGER PRIMARY KEY, user_id INTEGER, transaction_type TEXT, amount REAL, recipient TEXT, timestamp TEXT)"""
)
conn.commit()


class User:
    def __init__(self, id, username, wallet_id, balance):
        self.id = id
        self.username = username
        self.wallet_id = wallet_id
        self.balance = balance

    def deposit(self, amount):
        self.balance += amount
        c.execute("UPDATE users SET balance = ? WHERE id = ?", (self.balance, self.id))
        c.execute(
            "INSERT INTO transactions (user_id, transaction_type, amount, timestamp) VALUES (?, ?, ?, ?)",
            (self.id, "Deposit", amount, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        conn.commit()
        return f"${amount:.2f} has been added to your wallet."

    def transfer(self, recipient, amount):
        if self.balance >= amount:
            self.balance -= amount
            c.execute(
                "UPDATE users SET balance = balance + ? WHERE username = ?",
                (amount, recipient),
            )
            c.execute(
                "UPDATE users SET balance = ? WHERE id = ?", (self.balance, self.id)
            )
            c.execute(
                "INSERT INTO transactions (user_id, transaction_type, amount, recipient, timestamp) VALUES (?, ?, ?, ?, ?)",
                (
                    self.id,
                    "Transfer",
                    amount,
                    recipient,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )
            conn.commit()
            return f"Successfully transferred ${amount:.2f} to {recipient}."
        else:
            return "Insufficient balance!"

    def check_balance(self):
        return f"Your current balance is: ${self.balance:.2f}"

    def show_transaction_history(self):
        c.execute(
            "SELECT transaction_type, amount, recipient, timestamp FROM transactions WHERE user_id = ?",
            (self.id,),
        )
        transactions = c.fetchall()
        return pd.DataFrame(
            transactions, columns=["Type", "Amount", "Recipient", "Timestamp"]
        )

    def get_spending_data(self):
        c.execute(
            "SELECT transaction_type, amount, timestamp FROM transactions WHERE user_id = ? AND transaction_type = 'Transfer'",
            (self.id,),
        )
        transactions = c.fetchall()
        return pd.DataFrame(transactions, columns=["Type", "Amount", "Timestamp"])


def user_login(username, password):
    c.execute(
        "SELECT * FROM users WHERE username = ? AND password = ?", (username, password)
    )
    user = c.fetchone()
    if user:
        return User(user[0], user[1], user[3], user[4])
    return None


def main():
    st.set_page_config(page_title="E-Wallet App", page_icon="💰", layout="wide")
    st.title("E-Wallet Application")

    if "current_user" not in st.session_state:
        st.session_state.current_user = None
    if "page" not in st.session_state:
        st.session_state.page = "login"

    def logout():
        st.session_state.current_user = None
        st.session_state.page = "login"

    if st.session_state.current_user is None:
        if st.session_state.page == "login":
            st.subheader("Login")
            with st.form("login_form"):
                username = st.text_input("Enter username")
                password = st.text_input("Enter password", type="password")
                submit_button = st.form_submit_button("Login")

                if submit_button:
                    user = user_login(username, password)
                    if user:
                        st.session_state.current_user = user
                        st.success(f"Welcome {user.username}!")
                        st.session_state.page = "dashboard"
                        st.rerun()
                    else:
                        st.error("Invalid username or password")

            if st.button("Don't have an account? Register here"):
                st.session_state.page = "register"
                st.rerun()

        elif st.session_state.page == "register":
            st.subheader("Register")
            with st.form("register_form"):
                new_username = st.text_input("Choose a username")
                new_password = st.text_input("Choose a password", type="password")
                submit_button = st.form_submit_button("Register")

                if submit_button:
                    c.execute("SELECT * FROM users WHERE username = ?", (new_username,))
                    if c.fetchone():
                        st.error(
                            "Username already exists. Please choose a different one."
                        )
                    else:
                        wallet_id = uuid.uuid4().hex[:8]
                        c.execute(
                            "INSERT INTO users (username, password, wallet_id, balance) VALUES (?, ?, ?, ?)",
                            (new_username, new_password, wallet_id, 0.0),
                        )
                        conn.commit()
                        st.success("Registration successful! Please log in.")
                        st.session_state.page = "login"
                        st.rerun()

            if st.button("Already have an account? Login here"):
                st.session_state.page = "login"
                st.rerun()

    else:
        user = st.session_state.current_user
        st.sidebar.title(f"Welcome, {user.username}!")
        st.sidebar.text(f"Wallet ID: {user.wallet_id}")

        choice = st.sidebar.selectbox(
            "E-Wallet Menu",
            [
                "Deposit",
                "Transfer",
                "Balance",
                "History",
                "Spending Analysis",
                "Logout",
            ],
        )

        if choice == "Deposit":
            st.subheader("Deposit Money")
            amount = st.number_input(
                "Enter amount to deposit", min_value=0.01, step=0.01
            )
            if st.button("Deposit"):
                message = user.deposit(amount)
                st.success(message)

        elif choice == "Transfer":
            st.subheader("Transfer Money")
            c.execute(
                "SELECT username FROM users WHERE username != ?", (user.username,)
            )
            recipients = [row[0] for row in c.fetchall()]
            recipient_username = st.selectbox("Select recipient", recipients)
            amount = st.number_input(
                "Enter amount to transfer", min_value=0.01, step=0.01
            )
            if st.button("Transfer"):
                message = user.transfer(recipient_username, amount)
                if "Successfully" in message:
                    st.success(message)
                else:
                    st.error(message)

        elif choice == "Balance":
            st.subheader("Check Balance")
            st.info(user.check_balance())

        elif choice == "History":
            st.subheader("Transaction History")
            st.dataframe(user.show_transaction_history())

        elif choice == "Spending Analysis":
            st.subheader("Spending Analysis")
            spending_data = user.get_spending_data()
            if not spending_data.empty:
                spending_data["Timestamp"] = pd.to_datetime(spending_data["Timestamp"])
                spending_data["Date"] = spending_data["Timestamp"].dt.date
                daily_spending = (
                    spending_data.groupby("Date")["Amount"].sum().reset_index()
                )

                fig = px.line(
                    daily_spending,
                    x="Date",
                    y="Amount",
                    title="Daily Spending Over Time",
                )
                st.plotly_chart(fig)

                total_spent = spending_data["Amount"].sum()
                st.write(f"Total amount spent: ${total_spent:.2f}")

                avg_transaction = spending_data["Amount"].mean()
                st.write(f"Average transaction amount: ${avg_transaction:.2f}")
            else:
                st.write("No spending data available yet.")

        elif choice == "Logout":
            logout()
            st.success("Logged out successfully!")
            st.rerun()


if __name__ == "__main__":
    main()
