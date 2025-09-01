import { Request, Response } from 'express';
import { MessageService } from '../services/messageService';

export class MessagesController {
    private messageService: MessageService;

    constructor() {
        this.messageService = new MessageService();
    }

    public async sendMessage(req: Request, res: Response): Promise<Response> {
        try {
            const { recipient, message } = req.body;
            const response = await this.messageService.sendMessage(recipient, message);
            return res.status(200).json(response);
        } catch (error) {
            return res.status(500).json({ error: error.message });
        }
    }

    public async receiveMessage(req: Request, res: Response): Promise<Response> {
        try {
            const messageData = req.body;
            await this.messageService.processReceivedMessage(messageData);
            return res.status(200).send('Message received');
        } catch (error) {
            return res.status(500).json({ error: error.message });
        }
    }
}