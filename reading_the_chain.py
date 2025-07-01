import random
import json
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from web3.providers.rpc import HTTPProvider


def connect_to_eth():
    # 使用 Infura 主网作为例子（你也可以换成自己的）
    infura_token = "5e1abd5de2ac4dbda6e952eddc4394ca"  # 替换为你自己的
    infura_url = f"https://mainnet.infura.io/v3/5e1abd5de2ac4dbda6e952eddc4394ca"
    w3 = Web3(Web3.HTTPProvider(infura_url))
    return w3


def connect_with_middleware(contract_json):
    # 读取 JSON 文件中的 BSC 测试网合约信息
    with open(contract_json, "r") as f:
        contract_data = json.load(f)["bsc"]
    contract_address = Web3.to_checksum_address(contract_data["address"])
    abi = contract_data["abi"]

    # 使用公共节点连接 BNB 测试网
    rpc_url = "https://bsc-testnet.publicnode.com"
    w3 = Web3(HTTPProvider(rpc_url))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

    # 实例化合约对象
    contract = w3.eth.contract(address=contract_address, abi=abi)
    return w3, contract


def is_ordered_block(w3, block_num):
    block = w3.eth.get_block(block_num, full_transactions=True)
    base_fee = block.get("baseFeePerGas")
    txs = block["transactions"]

    def get_priority_fee(tx):
        # Type 2 transaction (post-EIP-1559)
        if tx.get("type") == "0x2" or tx.get("maxPriorityFeePerGas") is not None:
            max_priority = tx["maxPriorityFeePerGas"]
            max_fee = tx["maxFeePerGas"]
            if base_fee is None:
                return 0
            return min(max_priority, max_fee - base_fee)
        # Type 0 transaction (legacy)
        elif tx.get("gasPrice") is not None and base_fee is not None:
            return tx["gasPrice"] - base_fee
        elif tx.get("gasPrice") is not None:
            return tx["gasPrice"]
        else:
            return 0

    # 获取每个交易的 priority fee
    priority_fees = [get_priority_fee(tx) for tx in txs]

    # 判断是否按降序排列
    return priority_fees == sorted(priority_fees, reverse=True)


def get_contract_values(contract, admin_address, owner_address):
    default_admin_role = int.to_bytes(0, 32, byteorder="big")

    onchain_root = contract.functions.merkleRoot().call()
    has_role = contract.functions.hasRole(default_admin_role, Web3.to_checksum_address(admin_address)).call()
    prime = contract.functions.getPrimeByOwner(Web3.to_checksum_address(owner_address)).call()

    return onchain_root, has_role, prime


if __name__ == "__main__":
    admin_address = "0xAC55e7d73A792fE1A9e051BDF4A010c33962809A"
    owner_address = "0x793A37a85964D96ACD6368777c7C7050F05b11dE"
    contract_file = "contract_info.json"

    # connect_to_eth() 部分如果 Infura 没配好，可以注释掉
    try:
        eth_w3 = connect_to_eth()
        latest_block = eth_w3.eth.get_block_number()
        london_hard_fork_block_num = 12965000
        assert latest_block > london_hard_fork_block_num

        for _ in range(5):
            block_num = random.randint(1, latest_block)
            ordered = is_ordered_block(eth_w3, block_num)
            print(f"Block {block_num} is {'ordered' if ordered else 'not ordered'}")
    except Exception as e:
        print(f"[ETH Mainnet Part Skipped] Error: {e}")

    # BSC contract interaction
    try:
        cont_w3, contract = connect_with_middleware(contract_file)
        root, role, prime = get_contract_values(contract, admin_address, owner_address)
        print(f"onchain_root = {root}")
        print(f"has_role = {role}")
        print(f"prime = {prime}")
    except Exception as e:
        print(f"[BSC Contract Part Failed] Error: {e}")
