import axios from 'axios';

const INSTANCE_ID = process.env.ZAPI_INSTANCE_ID || '3E68FAC9BEFB716A85B5B24F68547F08';
const TOKEN = process.env.ZAPI_TOKEN || '6ED2B6C9FBB305ACA45EF6ED';
const BASE_URL = process.env.ZAPI_BASE_URL || 'https://api.z-api.io';

function buildUrl() {
    return `${BASE_URL}/instances/${INSTANCE_ID}/token/${TOKEN}/send-message`;
}

/**
 * Envia mensagem via Z-API
 * @param phone número com DDI (ex: "5511999998888")
 * @param message texto da mensagem
 */
export async function enviarMensagem(phone: string, message: string) {
    const url = buildUrl();
    const payload = {
        phone,
        message,
    };

    try {
        const resp = await axios.post(url, payload, { timeout: 10000 });
        return resp.data;
    } catch (err: any) {
        // normalize error
        const messageErr = err?.response?.data || err?.message || err;
        throw new Error(typeof messageErr === 'string' ? messageErr : JSON.stringify(messageErr));
    }
}