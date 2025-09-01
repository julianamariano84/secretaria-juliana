import axios from 'axios';
import { ZapiService } from './zapiService';

export class MessageService {
    private zapiService: ZapiService;

    constructor() {
        this.zapiService = new ZapiService();
    }

    async sendMessage(to: string, message: string): Promise<any> {
        const formattedMessage = this.formatMessage(message);
        const response = await this.zapiService.sendRequest({
            to,
            message: formattedMessage,
        });
        return response;
    }

    private formatMessage(message: string): string {
        // Here you can add any formatting logic needed for the message
        return message.trim();
    }

    async receiveMessage(data: any): Promise<void> {
        // Logic to handle incoming messages
        console.log('Received message:', data);
        // Process the message as needed
    }
}