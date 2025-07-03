import requests
import json
import os
import time # Importamos a biblioteca time

def _get_qkd_response(api_url, params, account_id, my_sae_id, kme_number):
    """
    Função auxiliar interna para executar a chamada à API QKD e tratar a resposta.
    """
    kme_host = f"kme-{kme_number}.acct-{account_id}.etsi-qkd-api.qukaydee.com"
    ca_cert_file = f"account-{account_id}-server-ca-qukaydee-com.crt"
    client_cert_file = f"{my_sae_id}.crt"
    client_key_file = f"{my_sae_id}.key"
    
    cert_files = [ca_cert_file, client_cert_file, client_key_file]
    for file_path in cert_files:
        if not os.path.exists(file_path):
            print(f"[ERRO] ({my_sae_id}) Ficheiro de certificado não encontrado: {file_path}")
            return None

    headers = {"Accept": "application/json"}
    full_api_url = f"https://{kme_host}{api_url}"
    
    try:
        response = requests.get(
            full_api_url,
            headers=headers,
            params=params,
            cert=(client_cert_file, client_key_file),
            verify=ca_cert_file
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"   (Falha na tentativa de comunicar com a API em {full_api_url}: {e})")
        return None

def request_new_key(account_id, my_sae_id, partner_sae_id, kme_number):
    """
    Função para a Alice: pede uma nova chave do endpoint /enc_keys.
    Retorna (key_id, key_material_b64) ou (None, None).
    """
    print(f"({my_sae_id} em kme-{kme_number}) -> Solicitando nova chave partilhada com {partner_sae_id}...")
    api_path = f"/api/v1/keys/{partner_sae_id}/enc_keys"
    params = {"number": 1, "size": 256}
    response_data = _get_qkd_response(api_path, params, account_id, my_sae_id, kme_number)
    if response_data:
        keys = response_data.get("keys", [])
        if keys:
            key_obj = keys[0]
            key_id = key_obj.get("key_ID")
            key_material_b64 = key_obj.get("key")
            if key_id and key_material_b64:
                print(f"({my_sae_id}) -> Chave recebida com sucesso! ID: {key_id}")
                return key_id, key_material_b64
    
    print(f"[ERRO] ({my_sae_id}) A resposta da API não continha a chave esperada.")
    return None, None

def get_key_by_id(account_id, my_sae_id, partner_sae_id, key_id_to_find, kme_number):
    """
    Função para o Bob: busca a sua cópia de uma chave usando o ID.
    Tenta várias vezes para lidar com possíveis atrasos de sincronização da API.
    """
    print(f"({my_sae_id} em kme-{kme_number}) -> Buscando chave com ID {key_id_to_find} partilhada com {partner_sae_id}...")
    
    # CORREÇÃO: O Bob deve aceder ao seu próprio endpoint.
    api_path = f"/api/v1/keys/{my_sae_id}/dec_keys"
    params = {"key_ID": key_id_to_find}
    
    max_retries = 3
    retry_delay_seconds = 2

    for attempt in range(max_retries):
        print(f"   (Tentativa {attempt + 1}/{max_retries})")
        response_data = _get_qkd_response(api_path, params, account_id, my_sae_id, kme_number)

        if response_data:
            keys = response_data.get("keys", [])
            if keys:
                key_obj = keys[0]
                key_material_b64 = key_obj.get("key")
                if key_material_b64:
                    print(f"({my_sae_id}) -> Chave com ID {key_id_to_find} recebida com sucesso!")
                    return key_material_b64

        if attempt < max_retries - 1:
            print(f"   Chave ainda não disponível. A aguardar {retry_delay_seconds}s para a próxima tentativa...")
            time.sleep(retry_delay_seconds)

    print(f"[ERRO] ({my_sae_id}) Não foi possível obter a chave com o ID especificado após {max_retries} tentativas.")
    return None