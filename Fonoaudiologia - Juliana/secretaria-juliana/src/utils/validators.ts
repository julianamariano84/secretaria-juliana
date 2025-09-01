export function validateAppointmentData(data: any): boolean {
    const { date, time, clientName } = data;
    if (!date || !time || !clientName) {
        return false;
    }
    // Additional validation logic can be added here
    return true;
}

export function validateMessageData(data: any): boolean {
    const { recipient, message } = data;
    if (!recipient || !message) {
        return false;
    }
    // Additional validation logic can be added here
    return true;
}

export function validateContactData(data: any): boolean {
    const { name, phone } = data;
    if (!name || !phone) {
        return false;
    }
    // Additional validation logic can be added here
    return true;
}