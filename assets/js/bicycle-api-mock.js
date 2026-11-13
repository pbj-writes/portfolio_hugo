// A mock of the Bicycle Inventory API that runs in the browser.
//
// The openapi shortcode loads this script so the "Try it" forms work without
// a server. The mock keeps its bicycles in memory, so changes last until the
// page reloads.
//
// It takes its rules from the same OpenAPI document that produces the page:
// which operations need an API key, which parameters and fields exist, and
// how to validate them. Only the behavior of each operation is written here.
(() => {
  "use strict";

  let bicycles = null;
  let nextId = 1;

  // Follows a local $ref, such as "#/components/schemas/BicycleInput".
  function resolve(spec, node) {
    if (!node || !node.$ref) return node;
    return node.$ref
      .split("/")
      .slice(1)
      .reduce((target, key) => target[key], spec);
  }

  function findOperation(spec, operationId) {
    for (const pathItem of Object.values(spec.paths)) {
      for (const operation of Object.values(pathItem)) {
        if (operation && operation.operationId === operationId) {
          const parameters = [...(pathItem.parameters ?? []), ...(operation.parameters ?? [])];
          return { operation, parameters: parameters.map((parameter) => resolve(spec, parameter)) };
        }
      }
    }
    return null;
  }

  function respond(status, body, headers = {}) {
    if (body === null) return { status, headers, body };
    return { status, headers: { "Content-Type": "application/json", ...headers }, body };
  }

  function problem(status, title, detail, errors) {
    const body = { title, status, detail };
    if (errors) body.errors = errors;
    return { status, headers: { "Content-Type": "application/problem+json" }, body };
  }

  function invalid(errors) {
    const count = errors.length;
    return problem(
      400,
      "Bad Request",
      `The request has ${count} validation ${count === 1 ? "error" : "errors"}.`,
      errors,
    );
  }

  // Checks a value against a schema. Returns a message, or null if it passes.
  function check(schema, value) {
    if (schema.type === "integer" && !Number.isInteger(value)) return "Must be an integer.";
    if (schema.type === "string" && typeof value !== "string") return "Must be a string.";
    if (schema.enum && !schema.enum.includes(value)) {
      return `Must be one of: ${schema.enum.join(", ")}.`;
    }
    if (schema.minimum !== undefined && value < schema.minimum) {
      return `Must be ${schema.minimum} or greater.`;
    }
    if (schema.maximum !== undefined && value > schema.maximum) {
      return `Must be ${schema.maximum} or less.`;
    }
    if (schema.minLength !== undefined && value.length < schema.minLength) {
      return schema.minLength === 1 ? "Must not be empty." : `Must be at least ${schema.minLength} characters.`;
    }
    if (schema.maxLength !== undefined && value.length > schema.maxLength) {
      return `Must be ${schema.maxLength} characters or fewer.`;
    }
    return null;
  }

  // Reads the path and query parameters the spec defines for an operation,
  // converting integers and filling in defaults.
  function readParameters(spec, parameters, request) {
    const values = {};
    const errors = [];
    for (const parameter of parameters) {
      const schema = resolve(spec, parameter.schema);
      const source = parameter.in === "path" ? request.pathParams : request.query;
      const raw = source[parameter.name];
      if (raw === undefined || raw === "") {
        if (parameter.required) errors.push({ field: parameter.name, message: "Required." });
        values[parameter.name] = schema.default;
        continue;
      }
      const value = schema.type === "integer" && /^-?\d+$/.test(raw) ? Number(raw) : raw;
      const message = check(schema, value);
      if (message) errors.push({ field: parameter.name, message });
      values[parameter.name] = value;
    }
    return { values, errors };
  }

  // Parses and validates a request body against the BicycleInput schema.
  function readBicycle(schema, text) {
    let input;
    try {
      input = JSON.parse(text);
    } catch {
      return { failure: problem(400, "Bad Request", "The request body isn't valid JSON.") };
    }
    if (input === null || typeof input !== "object" || Array.isArray(input)) {
      return { failure: problem(400, "Bad Request", "The request body must be a JSON object.") };
    }

    // Every field is required, so the "required" list is also the full list
    // of fields, in the order the spec presents them.
    const errors = [];
    const bicycle = {};
    for (const field of schema.required) {
      if (input[field] === undefined) {
        errors.push({ field, message: "Required." });
        continue;
      }
      const message = check(schema.properties[field], input[field]);
      if (message) errors.push({ field, message });
      bicycle[field] = input[field];
    }
    return errors.length ? { failure: invalid(errors) } : { bicycle };
  }

  // Puts the fields in the order the schema lists them, ID first.
  function inOrder(fields, id, source) {
    const bicycle = { bicycle_id: id };
    for (const field of fields) bicycle[field] = source[field];
    return bicycle;
  }

  window.openapiMock = (request, config) => {
    const { spec } = config;
    const found = findOperation(spec, request.operationId);
    if (!found) return problem(404, "Not Found", "The mock doesn't know this operation.");

    const inputSchema = spec.components.schemas.BicycleInput;
    const fields = inputSchema.required;

    if (bicycles === null) {
      bicycles = (config.seed ?? []).map((bicycle) => inOrder(fields, bicycle.bicycle_id, bicycle));
      nextId = Math.max(0, ...bicycles.map((bicycle) => bicycle.bicycle_id)) + 1;
    }

    // Operations that list a security requirement need the API key.
    for (const requirement of found.operation.security ?? []) {
      for (const name of Object.keys(requirement)) {
        const header = spec.components.securitySchemes[name].name;
        if (!config.demoKey || request.headers[header] !== config.demoKey) {
          return problem(
            401,
            "Unauthorized",
            `This operation requires a valid API key in the ${header} header.`,
          );
        }
      }
    }

    const { values, errors } = readParameters(spec, found.parameters, request);
    if (errors.length) return invalid(errors);

    const position = bicycles.findIndex((bicycle) => bicycle.bicycle_id === values.bicycleId);
    const notFound = () => problem(404, "Not Found", `No bicycle has the ID ${values.bicycleId}.`);

    switch (request.operationId) {
      case "listBicycles": {
        let matches = bicycles;
        if (values.make) {
          const make = values.make.toLowerCase();
          matches = matches.filter((bicycle) => bicycle.make.toLowerCase() === make);
        }
        const direction = values.order === "desc" ? -1 : 1;
        matches = [...matches].sort((a, b) => {
          const left = a[values.sort];
          const right = b[values.sort];
          const difference = typeof left === "string" ? left.localeCompare(right) : left - right;
          // Ties keep ascending ID order in both directions.
          return direction * difference || a.bicycle_id - b.bicycle_id;
        });
        return respond(200, {
          total_bicycles: matches.length,
          limit: values.limit,
          offset: values.offset,
          bicycles: matches.slice(values.offset, values.offset + values.limit),
        });
      }

      case "createBicycle": {
        const { bicycle, failure } = readBicycle(inputSchema, request.body);
        if (failure) return failure;
        const created = inOrder(fields, nextId++, bicycle);
        bicycles.push(created);
        return respond(201, created, { Location: `${config.server}/bicycles/${created.bicycle_id}` });
      }

      case "getBicycle":
        return position === -1 ? notFound() : respond(200, bicycles[position]);

      case "updateBicycle": {
        const { bicycle, failure } = readBicycle(inputSchema, request.body);
        if (failure) return failure;
        if (position === -1) return notFound();
        bicycles[position] = inOrder(fields, values.bicycleId, bicycle);
        return respond(200, bicycles[position]);
      }

      case "deleteBicycle":
        if (position === -1) return notFound();
        bicycles.splice(position, 1);
        return respond(204, null);

      default:
        return problem(404, "Not Found", "The mock doesn't know this operation.");
    }
  };
})();
