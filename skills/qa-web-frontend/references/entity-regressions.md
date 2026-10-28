# Entity, catalogue and pricing regression scenarios

Read for list-to-entity migrations, CRUD catalogues, price/tax changes, and records referenced by orders, workshop sheets, or bundles. Choose relevant cases, not every item.

## Validation and persistence

- Create a record with distinct name, accented description, decimal price/cost, a non-default tax rate where valid, and meaningful boolean flags. Reload and verify each field plus the generated identifier.
- Edit one field and several fields together; ensure untouched fields are preserved.
- Test empty versus whitespace-only required text. A rejected value should have understandable feedback and leave the user able to correct it.
- **Combine valid changes with one invalid input.** Example: change name and price while entering an out-of-range tax rate. Check the error, whether the editor stays open, and all persisted values. A rejected field plus saved sibling fields can be a confusing partial save even if invalid data itself was not stored. Do not infer a server transaction defect without backend evidence.
- Correct the input and save again. Verify that formatting/blur does not silently restore an old value or prevent the correction from persisting.
- Check zero, negative, fractional, upper-bound, and locale decimal input only where relevant to the field's intended rules. For price/tax fields, distinguish numeric validity from business-policy validity.
- If applicable, test Save-and-add-another resets the appropriate fields without duplicating the previous record. Do not retry ambiguous submissions until persistence has been inspected.

## Catalogue lifecycle

- Search by a distinctive substring and case variant. Verify filtered count and results after debounce settles; optionally test accents and no results if relevant.
- Verify sorting and pagination when the change affects them or the dataset is large enough. A small first page is not evidence that pagination works.
- Archive the QA entity: default active list should exclude it if that is the stated filter, archived/all views should expose the expected state, and restore should return it to eligible pickers.
- Inspect the actual selection dialog used by downstream workflows. Similar-looking inline free-text fields may not search the same catalogue. Treat undiscoverable entry points as UX feedback unless a promised workflow is broken.

## Prices and composed entities

Use simple values with an independently calculable expected outcome. For example, €12.34 net at 10% rounds to €13.57 gross. Record the rounding assumption when multiple lines can round differently.

- Compare edit fields, read-only detail, catalogue total, picker price and destination line. Missing VAT or gross price on detail can prevent users from detecting an incorrect save.
- For a pack/bundle, use quantity 2 to distinguish unit price from component total. Verify pack price versus the sum of components and any displayed discount. A pack's fixed price need not equal component sum.
- Test quantity boundaries and component addition/removal using QA records or unsaved forms, within current action permissions. Verify saved composition after reload.
- Check the destination's price, quantity, tax, labour/type flags where visible, and combined total. Do not infer transfer of hidden fields.

## Reference and historical-record behaviour

1. Insert a QA catalogue item into a new QA transaction or work record.
2. Verify the saved line and its price/tax/name.
3. Change the catalogue item's name and price; archive it if appropriate.
4. Reopen the destination and check whether historical values behave as specified.

Financial line values ordinarily need stable snapshots, but confirm the product's rule where ambiguous. Check active picker exclusion separately from preservation of existing references. Deletion of referenced entities, closed records, and issued invoices are distinct tests; do not claim them from an archive test on an open sheet.

For an actual data migration, browser checks establish representative readability and workflow behaviour only. Report whether a pre-migration baseline was available. Recommend separate count/field mapping reconciliation, old-record compatibility, tenant boundaries, and rerun safety when they remain untested.

## Lesson from the BikeCRM beta session

An invalid VAT edit produced `Indica un número válido`, closed the editor, saved the changed name and net price, and retained the old VAT after reload. A whitespace-only name similarly closed Edit while keeping the previous name. These motivate mixed-validity and persisted-state checks; they are examples, not assumptions about other applications.

Positive reference check: a service inserted at €13.57 with 10% VAT retained its original name, price and VAT after its catalogue entry was renamed, repriced and archived. Exercise both new-entity insertion and historical preservation when testing similar refactors.
