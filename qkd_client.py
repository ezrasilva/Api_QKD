import requests
import json
import os

def _get_qkd_response(api_url, params, account_id, my_sae_id, kme_number):
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
        print(f"[ERRO] ({my_sae_id}) Falha ao comunicar com a API QKD em {full_api_url}: {e}")
        return None

def request_new_key(account_id, my_sae_id, partner_sae_id, kme_number):
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
                return key_id, key_material_b64
    return None, None

def get_key_by_id(account_id, my_sae_id, partner_sae_id, key_id_to_find, kme_number):
    api_path = f"/api/v1/keys/{partner_sae_id}/dec_keys"
    params = {"key_ID": key_id_to_find}
    response_data = _get_qkd_response(api_path, params, account_id, my_sae_id, kme_number)
    if response_data:
        keys = response_data.get("keys", [])
        if keys:
            key_obj = keys[0]
            key_material_b64 = key_obj.get("key")
            if key_material_b64:
                return key_material_b64
    return None