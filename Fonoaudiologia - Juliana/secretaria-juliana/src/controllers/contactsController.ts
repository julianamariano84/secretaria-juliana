import { Request, Response } from 'express';

export class ContactsController {
    // Method to add a new contact
    public addContact(req: Request, res: Response): void {
        // Logic to add a contact
        res.status(201).send('Contact added successfully');
    }

    // Method to retrieve a contact by ID
    public getContact(req: Request, res: Response): void {
        const contactId = req.params.id;
        // Logic to retrieve a contact
        res.status(200).send(`Contact details for ID: ${contactId}`);
    }

    // Method to retrieve all contacts
    public getAllContacts(req: Request, res: Response): void {
        // Logic to retrieve all contacts
        res.status(200).send('List of all contacts');
    }
}