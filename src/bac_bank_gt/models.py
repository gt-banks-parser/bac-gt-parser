from bank_base_gt import (
    AbstractBankAccount,
    BaseBank,
    Bank,
    InvalidCredentialsException,
    Movement,
)
from bs4 import BeautifulSoup
from money import Money
import datetime
import logging
import re
import requests

BAC_ERRORS = {"INVALID_CREDENTIALS": "Usuario, contraseña, país o token inválido"}
logger = logging.getLogger(__name__)

session = requests.Session()
session.proxies = {
    "https": "https://100.76.174.3:3128",
    "http": "http://100.76.174.3:3128",
}


class BACBaseBank(BaseBank):
    def __init__(self):
        super().__init__(
            login_url="https://www1.sucursalelectronica.com/redir/redirect.go",
            accounts_url="https://www1.sucursalelectronica.com/ebac/module/consolidatedQuery/consolidatedQuery.go",
            movements_url="https://www1.sucursalelectronica.com/ebac/module/accountbalance/accountBalance.go",
            logout_url="https://www1.sucursalelectronica.com/ebac/common/logout.go",
        )


class BACBank(Bank):
    def __init__(self, credentials):
        super().__init__("BAC GT", BACBaseBank(), credentials, session=session)

    def login(self):

        r = self._fetch(
            self.login_url,
            {
                "country": "GT",
                "loginMode": "on",
                "product": self.credentials.username,
                "pass": self.credentials.password,
                "passtmp": self.credentials.password,
                "token": "",
                "signatureDataHash": "",
            },
            headers={
                "Host": "www1.sucursalelectronica.com",
                "Referer": "https://www1.sucursalelectronica.com/redir/showLogin.go",
                "Origin": "https://www1.sucursalelectronica.com",
                "Content-Type": "application/x-www-form-urlencoded",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-User": "?1",
                "Sec-GPC": "1",
                "Upgrade-Insecure-Requests": "1",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.5060.53 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
            },
        )
        logger.info("Did receive login response")
        bs = BeautifulSoup(r, features="html.parser")
        logger.info("Did parse login response")
        error_div = bs.find(
            "div", {"id": "balloonId", "class": "balloon balloon-ErrorType"}
        )
        if error_div:
            error_field = error_div.find("p")

            if (
                error_field
                and BAC_ERRORS["INVALID_CREDENTIALS"] in error_field.string.strip()
            ):
                error_string = error_field.string.strip()
                logger.error("Invalid Credentials: {0}".format(error_string))
                raise InvalidCredentialsException(error_string)

        logger.info("Did logged in succesfully")
        return True

    def fetch_accounts(self):
        accounts = []
        r = self._fetch(self.accounts_url)
        logger.info("Did received response from accounts url")

        bs = BeautifulSoup(r, features="html.parser")
        account_lines = bs.findAll("table")[0].findAll("tr")

        for line in account_lines:
            columns = line.findAll("td")
            if len(columns) > 4:
                productId = line.find("input", {"name": "productId"})
                account_bank_reference = None
                if productId.has_attr("value"):
                    account_bank_reference = productId["value"]
                acccount_id = columns[1].getText().strip()
                alias = " - ".join(
                    [part.strip() for part in columns[0].getText().strip().split("-")]
                )
                currency = columns[3].getText().strip().split("\t")[-1]
                account = BACBankAccount(
                    bank=self,
                    account_number=acccount_id,
                    alias=alias,
                    type="",
                    currency=currency,
                    account_bank_reference=account_bank_reference,
                )
                accounts.append(account)
                logger.info("Found account {0}".format(account))
        return accounts

    def get_account(self, number):
        accounts = self.fetch_accounts()
        for account in accounts:
            if account.account_number == number:
                return account

        return None

    def logout(self):
        r = self._fetch(self.logout_url)
        return True


class BACBankAccount(AbstractBankAccount):
    def fetch_movements(self, start_date, end_date):
        logging.info(
            "Will fetch movements data {1} - {0}".format(
                {
                    "productId": self.account_bank_reference,
                    "initDate": start_date.strftime("%d/%m/%Y"),
                    "endDate": end_date.strftime("%d/%m/%Y"),
                },
                self.bank.movements_url,
            )
        )
        movements = []
        r = self.bank._fetch(
            self.bank.movements_url,
            data={
                "productId": self.account_bank_reference,
                "initDate": start_date.strftime("%d/%m/%Y"),
                "endDate": end_date.strftime("%d/%m/%Y"),
                "initAmount": None,
                "limitAmount": None,
                "initReference": None,
                "endReference": None,
            },
            headers={
                "Origin": "https://www1.sucursalelectronica.com",
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
            },
        )
        logging.info(r)
        bs = BeautifulSoup(r, features="html5lib")
        table_body = bs.find("table", {"id": "transactions"}).find("tbody")
        if table_body:
            rows = table_body.find_all(
                lambda tag: "odd" in tag.get("class", "")
                or "even" in tag.get("class", "")
            )
            for row in rows:
                mov_title = row.find("span").text.strip()
                amount = 0
                date = row.select("td:nth-of-type(1)")[0].text.strip()
                date = datetime.datetime.strptime(date, "%d/%m/%Y")
                mov_id = row.select("td:nth-of-type(2)")[0].text.strip()

                debit_row = (
                    row.select("td:nth-of-type(5)")[0].text.strip().replace(",", "")
                )
                credit_row = (
                    row.select("td:nth-of-type(6)")[0].text.strip().replace(",", "")
                )
                balance_row = (
                    row.select("td:nth-of-type(7)")[0].text.strip().replace(",", "")
                )
                if debit_row == "0.00":
                    amount = Money(credit_row, currency="GTQ")
                else:
                    amount = -Money(debit_row, currency="GTQ")
                movement = Movement(self, mov_id, date, mov_title, amount)
                movement.balance = balance_row
                movement.account_balance = balance_row
                movements.append(movement)

        return movements
