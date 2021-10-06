from os import error
from bank_base_gt import (
    AbstractBankAccount,
    BaseBank,
    Bank,
    InvalidCredentialsException,
    Movement,
)
from bs4 import BeautifulSoup
from urllib.parse import parse_qs, quote_plus
import random
import string
from money import Money
import time
import datetime
import logging
import sys
import re

BAC_ERRORS = {"INVALID_CREDENTIALS": "Usuario, contraseña, país o token inválido"}
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)


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
        super().__init__("BAC GT", BACBaseBank(), credentials)

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
                "Origin": "https://www1.sucursalelectronica.com",
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
            },
        )
        logging.info("Did receive login response")
        bs = BeautifulSoup(r, features="html.parser")
        logging.info("Did parse login response")
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

        logging.info("Did logged in succesfully")
        return True

    def fetch_accounts(self):
        accounts = []
        r = self._fetch(self.accounts_url)
        logger.info("Did received response from accounts url")
        bs = BeautifulSoup(r, features="html.parser")
        account_lines = bs.find("table", {"id": re.compile("productTable.*")}).findAll(
            "tr"
        )

        for line in account_lines:
            columns = line.findAll("td")
            if len(columns) > 4:
                acccount_id = columns[1].getText().strip()
                alias = " - ".join(
                    [part.strip() for part in columns[0].getText().strip().split("-")]
                )
                currency = columns[3].getText().strip().split("\t")[-1]
                print(alias, acccount_id, currency)
                account = BACBankAccount(
                    bank=self,
                    account_number=acccount_id,
                    alias=alias,
                    type="",
                    currency=currency,
                )
                accounts.append(account)
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
    _FILE_NAME = "".join(random.choices(string.digits, k=8))
    _DEFAULT_HEADERS = {}

    def _convert_date_format(self, date_string):
        first_two = date_string[0:2]
        second_two = date_string[3:5]
        return "{0}/{1}/{2}".format(second_two, first_two, date_string[6:])

    def process_mov_line(self, line):
        pass

    def fetch_movements(self, start_date, end_date):
        movements = []
        return movements
