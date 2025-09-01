import request from 'supertest';
import app from '../../src/app'; // Ajuste o caminho conforme necessário

describe('Z-API Integration Tests', () => {
    const token = '9D1448816F95F132200BAE50'; // Token de integração

    it('should send a message successfully', async () => {
        const response = await request(app)
            .post('/api/messages/send') // Ajuste o endpoint conforme necessário
            .set('Authorization', `Bearer ${token}`)
            .send({
                to: '1234567890', // Número de telefone do destinatário
                message: 'Olá, esta é uma mensagem de teste!'
            });

        expect(response.status).toBe(200);
        expect(response.body).toHaveProperty('success', true);
    });

    it('should retrieve contacts successfully', async () => {
        const response = await request(app)
            .get('/api/contacts') // Ajuste o endpoint conforme necessário
            .set('Authorization', `Bearer ${token}`);

        expect(response.status).toBe(200);
        expect(response.body).toBeInstanceOf(Array);
    });

    // Adicione mais testes conforme necessário
});