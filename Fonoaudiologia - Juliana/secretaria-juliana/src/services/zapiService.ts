import axios from 'axios';

class ZapiService {
    private apiUrl: string;
    private token: string;

    constructor() {
        this.apiUrl = 'https://api.z-api.io/'; // URL base da Z-API
        this.token = '9D1448816F95F132200BAE50'; // Token de integração
    }

    private async sendRequest(endpoint: string, method: string, data?: any) {
        try {
            const response = await axios({
                method: method,
                url: `${this.apiUrl}${endpoint}`,
                headers: {
                    'Authorization': `Bearer ${this.token}`,
                    'Content-Type': 'application/json'
                },
                data: data
            });
            return response.data;
        } catch (error) {
            throw new Error(`Erro ao comunicar com a Z-API: ${error.message}`);
        }
    }

    public async sendMessage(to: string, message: string) {
        const endpoint = 'send-message'; // Endpoint para enviar mensagens
        const data = {
            to: to,
            message: message
        };
        return await this.sendRequest(endpoint, 'POST', data);
    }

    public async getMessages() {
        const endpoint = 'get-messages'; // Endpoint para obter mensagens
        return await this.sendRequest(endpoint, 'GET');
    }

    // Adicione outros métodos conforme necessário para interagir com a Z-API
}

export default ZapiService;