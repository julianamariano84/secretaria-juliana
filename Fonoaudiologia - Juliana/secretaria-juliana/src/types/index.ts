export interface Appointment {
    id: string;
    clientName: string;
    date: Date;
    time: string;
    notes?: string;
}

export interface Message {
    id: string;
    sender: string;
    recipient: string;
    content: string;
    timestamp: Date;
}

export interface Contact {
    id: string;
    name: string;
    phoneNumber: string;
    email?: string;
}

export interface ApiResponse<T> {
    success: boolean;
    data?: T;
    error?: string;
}