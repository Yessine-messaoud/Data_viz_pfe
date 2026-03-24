export class TableauJoinResolver {
    resolve(input) {
        return input.map((join) => ({
            id: join.id,
            left_table: join.leftTable,
            right_table: join.rightTable,
            type: join.joinType,
            keys: join.keys.map((key) => ({
                left: { table: join.leftTable, column: key.leftColumn },
                right: { table: join.rightTable, column: key.rightColumn },
            })),
        }));
    }
}
