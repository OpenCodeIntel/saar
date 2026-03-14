<!-- SAAR:AUTO-START -->
# Copilot Instructions -- saar

## Conventions

- Functions use `snake_case`
- Classes use `PascalCase`
- Files use `snake_case`

## Error Handling

Use existing exceptions: OCIAPIError, OCIAuthError.
Always log exceptions before re-raising.

## Testing

Use pytest. Test files match `test_*.py`.
Use unittest.mock for mocking.
<!-- SAAR:AUTO-END -->
