package edu.trusttrail.keycloak;

import java.util.List;

import org.keycloak.models.ClientSessionContext;
import org.keycloak.models.KeycloakSession;
import org.keycloak.models.ProtocolMapperModel;
import org.keycloak.models.UserSessionModel;
import org.keycloak.protocol.oidc.mappers.AbstractOIDCProtocolMapper;
import org.keycloak.protocol.oidc.mappers.OIDCAccessTokenMapper;
import org.keycloak.protocol.oidc.mappers.OIDCIDTokenMapper;
import org.keycloak.provider.ProviderConfigProperty;
import org.keycloak.representations.AccessToken;
import org.keycloak.representations.IDToken;

/**
 * Removes the SSO session ID ("sid") from ID and access tokens.
 *
 * Keycloak adds sid unconditionally, and every client in one SSO session gets
 * the same value, which lets colluding services link their pairwise pseudonyms.
 *
 * Side effects (acceptable for TrustTrail, documented in the README): the token
 * can no longer be tied to a session, so refresh tokens, the userinfo endpoint
 * and id_token_hint logout stop working for clients that carry this mapper.
 * The seed script turns refresh tokens off for those clients.
 */
public class StripSessionIdMapper extends AbstractOIDCProtocolMapper
        implements OIDCAccessTokenMapper, OIDCIDTokenMapper {

    public static final String PROVIDER_ID = "trusttrail-strip-sid-mapper";

    @Override
    public String getId() {
        return PROVIDER_ID;
    }

    @Override
    public String getDisplayType() {
        return "TrustTrail: strip session ID (sid)";
    }

    @Override
    public String getDisplayCategory() {
        return TOKEN_MAPPER_CATEGORY;
    }

    @Override
    public String getHelpText() {
        return "Removes the sid claim so services in one SSO session cannot link pseudonyms.";
    }

    @Override
    public List<ProviderConfigProperty> getConfigProperties() {
        return List.of();
    }

    // Overridden directly (not via setClaim) so it applies regardless of the
    // "add to access/ID token" switches, which this mapper does not offer.
    @Override
    public AccessToken transformAccessToken(AccessToken token, ProtocolMapperModel mappingModel,
            KeycloakSession session, UserSessionModel userSession, ClientSessionContext clientSessionCtx) {
        token.setSessionId(null);
        return token;
    }

    @Override
    public IDToken transformIDToken(IDToken token, ProtocolMapperModel mappingModel,
            KeycloakSession session, UserSessionModel userSession, ClientSessionContext clientSessionCtx) {
        token.setSessionId(null);
        return token;
    }
}
