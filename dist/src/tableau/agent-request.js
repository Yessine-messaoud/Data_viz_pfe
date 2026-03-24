export class DefaultAgentRequestBuilder {
    build(parsedWorkbook, intent, config) {
        return {
            parsedWorkbook,
            intent,
            config,
        };
    }
}
