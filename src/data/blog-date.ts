export function koreanDate(date: string) {
	const parsed = new Date(`${date} UTC`);
	if (Number.isNaN(parsed.getTime())) return undefined;
	return parsed.toLocaleDateString('ko-KR', { dateStyle: 'long', timeZone: 'UTC' });
}
