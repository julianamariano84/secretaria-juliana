import axios from 'axios';
import { ZapiService } from '../../services/zapiService';

const ZAPI_TOKEN = '9D1448816F95F132200BAE50';
const ZAPI_URL = 'https://api.z-api.io/'; // URL base da Z-API

export class ZapiIntegration {
    private zapiService: ZapiService;

    constructor() {
        this.zapiService = new ZapiService(ZAPI_URL, ZAPI_TOKEN);
    }

    public async sendMessage(to: string, message: string): Promise<any> {
        const payload = {
            to,
            message,
        };
        return this.zapiService.sendRequest('/send-message', payload);
    }

    public async getMessages(): Promise<any> {
        return this.zapiService.sendRequest('/get-messages');
    }

    public async getContacts(): Promise<any> {
        return this.zapiService.sendRequest('/get-contacts');
    }
}